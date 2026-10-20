
import socket
import struct
import threading

HOST = "0.0.0.0"
PORT = 5000
CHUNK_SIZE = 64 * 1024
MAX_FRAME_SIZE = 10 * 1024 * 1024


def receive_exact(conn, size):
    data = bytearray()

    while len(data) < size:
        chunk = conn.recv(min(CHUNK_SIZE, size - len(data)))

        if not chunk:
            raise ConnectionError("Connection closed")

        data.extend(chunk)

    return bytes(data)


def receive_role(conn):
    data = bytearray()

    while len(data) < 32:
        char = conn.recv(1)

        if not char:
            raise ConnectionError("Client disconnected")

        if char == b"\n":
            return data.decode("ascii")

        data.extend(char)

    raise ValueError("Invalid role")


def relay(source, receiver, sender_id, send_lock):
    ended = False

    try:
        while True:
            # The sender sends a 4-byte frame length
            header = receive_exact(source, 4)
            frame_size = struct.unpack("!I", header)[0]

            if frame_size > MAX_FRAME_SIZE:
                raise ValueError("Frame is too large")

            if frame_size == 0:
                with send_lock:
                    receiver.sendall(struct.pack("!BI", sender_id, 0))
                ended = True
                break

            frame = receive_exact(source, frame_size)

            # Packet: 1-byte sender ID + 4-byte length + frame
            packet = struct.pack("!BI", sender_id, frame_size) + frame

            # Prevent packets from the two senders mixing together
            with send_lock:
                receiver.sendall(packet)

    except (ConnectionError, OSError, ValueError) as error:
        print(f"Client {sender_id} relay stopped:", error)

    finally:
        if not ended:
            try:
                with send_lock:
                    receiver.sendall(struct.pack("!BI", sender_id, 0))
            except OSError:
                pass


def main():
    clients = {}

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((HOST, PORT))
        server.listen(3)

        print("Server listening on port", PORT)

        try:
            # Wait for Client 1, Client 2, and Client 3
            while len(clients) < 3:
                conn, address = server.accept()

                try:
                    role = receive_role(conn)

                    if role not in ("CLIENT1", "CLIENT2", "CLIENT3"):
                        conn.close()
                        continue

                    if role in clients:
                        conn.close()
                        print("Duplicate role:", role)
                        continue

                    clients[role] = conn
                    print(role, "connected from", address)

                except Exception:
                    conn.close()
                    raise

            client1 = clients["CLIENT1"]
            client2 = clients["CLIENT2"]
            client3 = clients["CLIENT3"]

            # Tell everyone that all three clients are connected
            for conn in clients.values():
                conn.sendall(b"READY\n")

            send_lock = threading.Lock()

            t1 = threading.Thread(
                target=relay,
                args=(client1, client3, 1, send_lock)
            )

            t2 = threading.Thread(
                target=relay,
                args=(client2, client3, 2, send_lock)
            )

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            print("Both streams ended")

        finally:
            for conn in clients.values():
                try:
                    conn.close()
                except OSError:
                    pass


if __name__ == "__main__":
    main()

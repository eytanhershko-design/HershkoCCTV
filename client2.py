
import socket
import struct
import numpy as np
import cv2

SERVER_IP = "127.0.0.1"  # Server on this same computer
PORT = 5000

CHUNK_SIZE = 64 * 1024


def receive_exact(conn, size):
    data = bytearray()

    while len(data) < size:
        chunk = conn.recv(min(CHUNK_SIZE, size - len(data)))

        if not chunk:
            raise ConnectionError("Server disconnected")

        data.extend(chunk)

    return bytes(data)


def main():
    ended = set()

    with socket.create_connection((SERVER_IP, PORT)) as client:
        client.sendall(b"CLIENT3\n")

        response = bytearray()

        while not response.endswith(b"\n"):
            chunk = client.recv(1)

            if not chunk:
                raise ConnectionError("Server disconnected")

            response.extend(chunk)

        if response != b"READY\n":
            raise ConnectionError("Server is not ready")

        print("Receiving both videos. Press Q to quit.")

        try:
            while len(ended) < 2:
                # Read sender ID (1 byte) and frame length (4 bytes)
                header = receive_exact(client, 5)
                sender_id, frame_size = struct.unpack("!BI", header)

                if sender_id not in (1, 2):
                    raise ValueError("Unknown sender ID")

                if frame_size == 0:
                    ended.add(sender_id)
                    print(f"Client {sender_id} finished sending")
                    continue

                frame_bytes = receive_exact(client, frame_size)

                encoded = np.frombuffer(
                    frame_bytes,
                    dtype=np.uint8
                )

                frame = cv2.imdecode(
                    encoded,
                    cv2.IMREAD_COLOR
                )

                if frame is not None:
                    window_name = f"Video from Client {sender_id}"
                    cv2.imshow(window_name, frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            print("Both videos finished")

        finally:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Client 3 error:", error)
    finally:
        cv2.destroyAllWindows()

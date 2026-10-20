
import socket
import struct
import threading
import queue
import time
import cv2

SERVER_IP = "192.168.1.100"  # Replace with the server computer's IP
PORT = 5000

ROLE = "CLIENT1"  # On the other computer, change to CLIENT2

DURATION_SECONDS = 10
QUEUE_SIZE = 2

frame_queue = queue.Queue(maxsize=QUEUE_SIZE)
stop_event = threading.Event()


def send_video(client):
    try:
        while True:
            frame_bytes = frame_queue.get()

            if frame_bytes is None:
                break

            header = struct.pack("!I", len(frame_bytes))
            client.sendall(header + frame_bytes)

        # A zero length means the video has ended
        client.sendall(struct.pack("!I", 0))

    except (OSError, ConnectionError) as error:
        print("Sending error:", error)
        stop_event.set()


def main():
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Could not open camera")
        return

    try:
        with socket.create_connection((SERVER_IP, PORT)) as client:
            client.sendall((ROLE + "\n").encode("ascii"))

            response = bytearray()

            while not response.endswith(b"\n"):
                chunk = client.recv(1)

                if not chunk:
                    raise ConnectionError("Server disconnected")

                response.extend(chunk)

            if response != b"READY\n":
                raise ConnectionError("Server is not ready")

            print("Camera started. Press Q to stop.")

            sender = threading.Thread(
                target=send_video,
                args=(client,)
            )
            sender.start()

            start_time = time.monotonic()

            try:
                while (
                    time.monotonic() - start_time < DURATION_SECONDS
                    and not stop_event.is_set()
                ):
                    ret, frame = cap.read()

                    if not ret:
                        print("Could not read camera frame")
                        break

                    # Show the local camera
                    cv2.imshow(f"{ROLE} - My Camera", frame)

                    # Encode the frame as JPEG
                    success, encoded = cv2.imencode(
                        ".jpg",
                        frame,
                        [cv2.IMWRITE_JPEG_QUALITY, 80]
                    )

                    if success:
                        frame_bytes = encoded.tobytes()

                        # Keep only recent frames if sending is slower
                        if frame_queue.full():
                            try:
                                frame_queue.get_nowait()
                            except queue.Empty:
                                pass

                        try:
                            frame_queue.put_nowait(frame_bytes)
                        except queue.Full:
                            pass

                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        break

            finally:
                # Tell the sender thread to finish after queued frames
                if sender.is_alive():
                    frame_queue.put(None)
                    sender.join()

    finally:
        stop_event.set()
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("Sender error:", error)

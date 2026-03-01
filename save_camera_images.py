import cv2
import argparse
import os


def main():
    parser = argparse.ArgumentParser(
        description="Capture an image from a camera and save it."
    )
    parser.add_argument(
        "-i", "--input", type=int, required=True, help="input camera device id"
    )
    parser.add_argument(
        "-n",
        "--name",
        type=str,
        required=True,
        help="name to save the image (e.g., front)",
    )
    parser.add_argument(
        "-r", "--resolution", default="1280x720", help="resolution of the camera image"
    )
    args = parser.parse_args()

    W, H = [int(x) for x in args.resolution.split("x")]

    cap = cv2.VideoCapture(args.input)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, W)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, H)

    if not cap.isOpened():
        print(f"Cannot open camera {args.input}")
        return

    img_dir = "images"
    if not os.path.exists(img_dir):
        os.makedirs(img_dir)

    filename = os.path.join(img_dir, f"{args.name}.png")

    print("Press 's' to save the image.")
    print("Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            break

        cv2.imshow(f"Camera {args.input} - {args.name}", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("s"):
            cv2.imwrite(filename, frame)
            print(f"Image saved to {filename}")
            break
        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

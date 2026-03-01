import cv2
import numpy as np
import os


class PanoramicStitcher:
    def __init__(
        self,
        car_image_path="images/car-top-view.jpg",
        calib_data_folder="calibration_data",
        output_size=(800, 1000),
        car_size=(180, 380),
    ):
        """
        Initializes the PanoramicStitcher.
        :param car_image_path: Path to the car's top-view image.
        :param calib_data_folder: Folder containing calibration and perspective files.
        :param output_size: Tuple (width, height) of the final panorama.
        :param car_size: Tuple (width, height) to resize the car image to.
        """
        self.camera_positions = ["front", "back", "left", "right"]
        self.perspective_matrices = {}
        self.camera_matrices = {}
        self.dist_coeffs = {}

        # Load car image
        self.car_image = cv2.imread(car_image_path)
        if self.car_image is not None:
            self.car_image = cv2.resize(self.car_image, car_size)
            print("Successfully loaded car image.")
        else:
            print(f"Warning: Could not load car image from {car_image_path}")

        self.panorama_width, self.panorama_height = output_size
        self.car_width, self.car_height = car_size

        # Load calibration and perspective transformation data
        for pos in self.camera_positions:
            try:
                calib_path = os.path.join(
                    calib_data_folder, f"{pos}_calibration_data.npz"
                )
                persp_path = os.path.join(
                    calib_data_folder, f"{pos}_perspective_matrix.npy"
                )
                with np.load(calib_path) as data:
                    self.camera_matrices[pos] = data["mtx"]
                    self.dist_coeffs[pos] = data["dist"]
                self.perspective_matrices[pos] = np.load(persp_path)
                print(
                    f"Loaded calibration data and perspective matrix for '{pos}' camera."
                )
            except FileNotFoundError:
                self.perspective_matrices[pos] = None
                self.camera_matrices[pos] = None
                self.dist_coeffs[pos] = None
                print(
                    f"Warning: Calibration or perspective file not found for '{pos}' camera."
                )

        self._create_blur_blend_masks()

    def _create_blur_blend_masks(self):
        """
        Creates blending masks using blurred rectangles for a smooth,
        multi-band blending effect.
        """
        self.masks = {}
        pw, ph = self.panorama_width, self.panorama_height
        cw, ch = self.car_width, self.car_height
        car_x_s, car_y_s = (pw - cw) // 2, (ph - ch) // 2
        car_x_e, car_y_e = car_x_s + cw, car_y_s + ch

        # Kernel size for Gaussian blur - this controls the blend width (must be odd)
        blur_kernel_size = 151

        # Create a binary mask for each region
        mask_f = np.zeros((ph, pw), dtype=np.float32)
        mask_f[0:car_y_s, :] = 1.0

        mask_b = np.zeros((ph, pw), dtype=np.float32)
        mask_b[car_y_e:, :] = 1.0

        mask_l = np.zeros((ph, pw), dtype=np.float32)
        mask_l[:, 0:car_x_s] = 1.0

        mask_r = np.zeros((ph, pw), dtype=np.float32)
        mask_r[:, car_x_e:] = 1.0

        # Blur each mask to create smooth edges
        mask_f = cv2.GaussianBlur(mask_f, (blur_kernel_size, blur_kernel_size), 0)
        mask_b = cv2.GaussianBlur(mask_b, (blur_kernel_size, blur_kernel_size), 0)
        mask_l = cv2.GaussianBlur(mask_l, (blur_kernel_size, blur_kernel_size), 0)
        mask_r = cv2.GaussianBlur(mask_r, (blur_kernel_size, blur_kernel_size), 0)

        # Normalize the masks so they sum to 1 at each pixel
        total_mask = mask_f + mask_b + mask_l + mask_r
        # Avoid division by zero in the car area, though it's unlikely with blur
        total_mask[total_mask == 0] = 1.0

        self.masks["front"] = cv2.cvtColor(mask_f / total_mask, cv2.COLOR_GRAY2BGR)
        self.masks["back"] = cv2.cvtColor(mask_b / total_mask, cv2.COLOR_GRAY2BGR)
        self.masks["left"] = cv2.cvtColor(mask_l / total_mask, cv2.COLOR_GRAY2BGR)
        self.masks["right"] = cv2.cvtColor(mask_r / total_mask, cv2.COLOR_GRAY2BGR)

    def stitch(self, frames):
        warped = {}
        for pos in self.camera_positions:
            frame = frames.get(pos)
            M, mtx, dist = (
                self.perspective_matrices.get(pos),
                self.camera_matrices.get(pos),
                self.dist_coeffs.get(pos),
            )
            if frame is None or M is None or mtx is None or dist is None:
                warped[pos] = np.zeros(
                    (self.panorama_height, self.panorama_width, 3), dtype=np.float32
                )
                continue

            undistorted = cv2.undistort(frame, mtx, dist, None, mtx)
            warped[pos] = cv2.warpPerspective(
                undistorted, M, (self.panorama_width, self.panorama_height)
            ).astype(np.float32)

        # Combine the four views using the masks
        panorama_canvas = (
            warped["front"] * self.masks["front"]
            + warped["back"] * self.masks["back"]
            + warped["left"] * self.masks["left"]
            + warped["right"] * self.masks["right"]
        )

        if self.car_image is not None:
            car_x, car_y = (self.panorama_width - self.car_width) // 2, (
                self.panorama_height - self.car_height
            ) // 2
            panorama_canvas[
                car_y : car_y + self.car_height, car_x : car_x + self.car_width
            ] = self.car_image.astype(np.float32)

        return np.clip(panorama_canvas, 0, 255).astype(np.uint8)


def create_dummy_calibration_files(data_folder="calibration_data"):
    """
    Generates a set of more realistic and tunable dummy calibration files.
    The user MUST tune these parameters based on their physical setup.
    """
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)

    # --- Step 1: Define panorama and camera properties ---
    PANO_WIDTH, PANO_HEIGHT = 800, 1000
    CAR_WIDTH_IN_PANO, CAR_HEIGHT_IN_PANO = 180, 380
    CAM_WIDTH, CAM_HEIGHT = 1280, 720

    # --- Step 2: Define Destination Points (where the warped image will fit) ---
    car_x_start = (PANO_WIDTH - CAR_WIDTH_IN_PANO) // 2
    car_y_start = (PANO_HEIGHT - CAR_HEIGHT_IN_PANO) // 2
    car_x_end = car_x_start + CAR_WIDTH_IN_PANO
    car_y_end = car_y_start + CAR_HEIGHT_IN_PANO

    front_dst = np.float32(
        [[0, 0], [PANO_WIDTH, 0], [car_x_start, car_y_start], [car_x_end, car_y_start]]
    )
    back_dst = np.float32(
        [
            [car_x_start, car_y_end],
            [car_x_end, car_y_end],
            [0, PANO_HEIGHT],
            [PANO_WIDTH, PANO_HEIGHT],
        ]
    )
    left_dst = np.float32(
        [[0, 0], [car_x_start, car_y_start], [0, PANO_HEIGHT], [car_x_start, car_y_end]]
    )
    right_dst = np.float32(
        [
            [car_x_end, car_y_start],
            [PANO_WIDTH, 0],
            [car_x_end, car_y_end],
            [PANO_WIDTH, PANO_HEIGHT],
        ]
    )

    # --- Step 3: !!! TUNE THESE SOURCE POINTS !!! ---
    # Define the source trapezoid from each *UNDISTORTED* camera feed.
    # These are the most critical values to adjust based on your camera's view.
    # Format for getPerspectiveTransform: np.float32([top-left, top-right, bottom-left, bottom-right])

    # For FRONT camera: A trapezoid from the bottom-center of the view.
    f_top_y, f_bot_y = 480, 700
    f_top_w, f_bot_w = 260, 1080
    f_top_x, f_bot_x = (CAM_WIDTH - f_top_w) // 2, (CAM_WIDTH - f_bot_w) // 2
    front_src = np.float32(
        [
            [f_top_x, f_top_y],
            [f_top_x + f_top_w, f_top_y],
            [f_bot_x, f_bot_y],
            [f_bot_x + f_bot_w, f_bot_y],
        ]
    )

    # For BACK camera: A similar trapezoid.
    back_src = np.copy(front_src)

    # For LEFT camera: A trapezoid from the right side of the view.
    l_top_x, l_bot_x = 900, 1280
    l_top_h, l_bot_h = 400, 720
    l_top_y, l_bot_y = (CAM_HEIGHT - l_top_h) // 2, (CAM_HEIGHT - l_bot_h) // 2
    left_src = np.float32(
        [
            [l_top_x, l_top_y],
            [l_bot_x, l_bot_y],
            [l_top_x, l_top_y + l_top_h],
            [l_bot_x, l_bot_y + l_bot_h],
        ]
    )

    # For RIGHT camera: A trapezoid from the left side of the view.
    r_top_x, r_bot_x = 380, 0
    r_top_h, r_bot_h = 400, 720
    r_top_y, r_bot_y = (CAM_HEIGHT - r_top_h) // 2, (CAM_HEIGHT - r_bot_h) // 2
    right_src = np.float32(
        [
            [r_top_x, r_top_y],
            [r_bot_x, r_bot_y],
            [r_top_x, r_top_y + r_top_h],
            [r_bot_x, r_bot_y + r_bot_h],
        ]
    )

    # --- Step 4: Generate and Save Matrices ---
    matrices = {
        "front": cv2.getPerspectiveTransform(front_src, front_dst),
        "back": cv2.getPerspectiveTransform(back_src, back_dst),
        "left": cv2.getPerspectiveTransform(left_src, left_dst),
        "right": cv2.getPerspectiveTransform(right_src, right_dst),
    }

    for pos, M in matrices.items():
        persp_path = os.path.join(data_folder, f"{pos}_perspective_matrix.npy")
        np.save(persp_path, M)
        print(f"Created dummy perspective file: {persp_path}")

    # --- Step 5: Define and Save Camera Intrinsic Parameters ---
    # !!! TUNE THESE as well if you have calibration data !!!
    # For now, we use generic fisheye parameters.
    # You should get these from `cv2.fisheye.calibrate`
    dummy_mtx = np.array([[800, 0, CAM_WIDTH / 2], [0, 800, CAM_HEIGHT / 2], [0, 0, 1]])
    # For fisheye, you often only need the first one or two distortion coefficients (k1, k2)
    dummy_dist = np.array([0.1, -0.05, 0, 0])

    for pos in ["front", "back", "left", "right"]:
        calib_path = os.path.join(data_folder, f"{pos}_calibration_data.npz")
        if not os.path.exists(calib_path):
            np.savez(calib_path, mtx=dummy_mtx, dist=dummy_dist)
            print(f"Created dummy calibration file: {calib_path}")


if __name__ == "__main__":
    # Run this file directly to generate dummy calibration files.
    print("Creating dummy calibration files for testing...")
    create_dummy_calibration_files()
    print("Done.")

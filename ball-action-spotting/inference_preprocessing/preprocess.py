import cv2
from src.ball_action import constants

def preprocess_video(video_path : Path):
  cap = cv2.VideoCapture(video_path)
  fps = cv2.get(cv2.CAP_PROP_FPS)
  output_file = constants.inference_dir \ 'output.mp4'
  output_fps = 25
  fourcc = cv2.VideoWriter_fourcc(*'mp4v')
  out = cv2.VideoWriter(output_file, fourcc, output_fps, (int(cap.get(3)), int(cap.get(4))))
  while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break
    out.write(frame)
    cap.release()
out.release()
cv2.destroyAllWindows()

import argparse
from pathlib import Path
from tqdm import tqdm
import numpy as np
import sys
import os
sys.path.append(os.getcwd())

from src.ball_action.annotations import raw_predictions_to_actions, prepare_game_spotting_results
from src.utils import get_best_model_path, get_video_info
from src.predictors import MultiDimStackerPredictor
from src.frame_fetchers import OpencvFrameFetcher
from src.ball_action import constants


RESOLUTION = "720p"
INDEX_SAVE_ZONE = 1
TTA = True


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", required=False, type=str)
    parser.add_argument('--video_id', required=True,type=str)
    parser.add_argument("--folds", default="all", type=str)
    parser.add_argument("--gpu_id", default=0, type=int)
    parser.add_argument("--challenge", action="store_true")
    parser.add_argument("--use_saved_predictions", action="store_true")
    return parser.parse_args()


def get_raw_predictions(predictor: MultiDimStackerPredictor,
                        video_path: Path,
                        frame_count: int) -> tuple[list[int], np.ndarray]:
    frame_fetcher = OpencvFrameFetcher(video_path, gpu_id=predictor.device.index)
    frame_fetcher.num_frames = frame_count

    indexes_generator = predictor.indexes_generator
    min_frame_index = indexes_generator.clip_index(0, frame_count, INDEX_SAVE_ZONE)
    max_frame_index = indexes_generator.clip_index(frame_count, frame_count, INDEX_SAVE_ZONE)
    frame_index2prediction = dict()
    predictor.reset_buffers()
    with tqdm() as t:
        while True:
            frame = frame_fetcher.fetch_frame()
            frame_index = frame_fetcher.current_index
            prediction, predict_index = predictor.predict(frame, frame_index)
            if predict_index < min_frame_index:
                continue
            if prediction is not None:
                frame_index2prediction[predict_index] = prediction.cpu().numpy()
            t.update()
            if predict_index == max_frame_index:
                break
    predictor.reset_buffers()
    frame_indexes = sorted(frame_index2prediction.keys())
    raw_predictions = np.stack([frame_index2prediction[i] for i in frame_indexes], axis=0)
    return frame_indexes, raw_predictions


def predict_video(predictor: MultiDimStackerPredictor,
                  half: int,
                  game_dir: Path,
                  game_prediction_dir: Path,
                  use_saved_predictions: bool,
                  video_id : str) -> dict[str, tuple]:
    # video_path = game_dir / f"{RESOLUTION}.{constants.videos_extension}" #f"{half}_{RESOLUTION}.mkv"
    video_path = game_dir / video_id
    video_info = get_video_info(video_path)
    print("Video info:", video_info)
    assert video_info["fps"] == constants.video_fps

    # raw_predictions_path = game_prediction_dir / f"{half}_raw_predictions.npz"
    raw_predictions_path = game_prediction_dir / f"{video_id}_raw_predictions.npz"

    if use_saved_predictions:
        with np.load(str(raw_predictions_path)) as raw_predictions:
            frame_indexes = raw_predictions["frame_indexes"]
            raw_predictions = raw_predictions["raw_predictions"]
    else:
        print("Predict video:", video_path)
        frame_indexes, raw_predictions = get_raw_predictions(
            predictor, video_path, video_info["frame_count"]
        )
        np.savez(
            raw_predictions_path,
            frame_indexes=frame_indexes,
            raw_predictions=raw_predictions,
        )
        print("Raw predictions saved to", raw_predictions_path)

    class2actions = raw_predictions_to_actions(frame_indexes, raw_predictions)
    return class2actions


def predict_game(predictor: MultiDimStackerPredictor,
                 game: str,
                 prediction_dir: Path,
                 use_saved_predictions: bool):
    game_dir = constants.soccernet_dir / game
    game_prediction_dir = prediction_dir / game
    game_prediction_dir.mkdir(parents=True, exist_ok=True)
    print("Predict game:", game)

    half2class_actions = dict()
    for half in constants.halves:
        class_actions = predict_video(
            predictor, half, game_dir, game_prediction_dir, use_saved_predictions
        )
        half2class_actions[half] = class_actions

    prepare_game_spotting_results(half2class_actions, game, prediction_dir)




if __name__ == "__main__":
    args = parse_arguments()
    predictor = MultiDimStackerPredictor(constants.model_path, device=f"cuda:{args.gpu_id}", tta=TTA)
    predict_video(
        predictor=predictor,
        half = 1 , 
        game_dir = constants.inference_dir,
        game_prediction_dir = constants.predictions_dir,
        used_saved_predictions = False,
        video_id = args.video_id
    
    )



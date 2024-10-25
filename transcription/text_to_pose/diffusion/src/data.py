from random import shuffle
from typing import List, TypedDict

import torch
from pose_format import Pose
from torch.utils.data import Dataset

from _shared.tfds_dataset import ProcessedPoseDatum, get_tfds_dataset


class TextPoseDatum(TypedDict):
    id: str
    text: str
    pose: Pose
    length: int


class TextPoseDataset(Dataset):

    def __init__(self, data: List[TextPoseDatum]):
        self.data = data

    def __len__(self):
        return len(self.data)

    def __getitem__(self, index):
        datum = self.data[index]
        pose = datum["pose"]

        torch_body = pose.body.torch()
        pose_length = len(torch_body.data)

        return {
            "id": datum["id"],
            "text": datum["text"],
            "pose": {
                "obj": pose,
                "data": torch_body.data.tensor[:, 0, :, :],
                "confidence": torch_body.confidence[:, 0, :],
                "length": torch.tensor([pose_length], dtype=torch.float),
                "inverse_mask": torch.ones(pose_length, dtype=torch.int8)
            }
        }


def process_datum(datum: ProcessedPoseDatum) -> List[TextPoseDatum]:
    if "hamnosys" in datum["tf_datum"]:
        text = datum["tf_datum"]["hamnosys"].numpy().decode('utf-8').strip()
    else:
        text = ""

    if "pose" in datum:
        poses: List[Pose] = [datum["pose"]]
    elif "views" in datum:
        poses: List[Pose] = datum["views"]["pose"]
    else:
        raise ValueError("No pose found in datum")

    data = []
    for pose in poses:
        pose.body.data = pose.body.data[:, :, :, :3]  # X,Y,Z
        # Prune all leading frames containing only zeros
        for i in range(len(pose.body.data)):
            if pose.body.confidence[i].sum() != 0:
                if i != 0:
                    pose.body.data = pose.body.data[i:]
                    pose.body.confidence = pose.body.confidence[i:]
                break

        data.append({"id": datum["id"], "text": text, "pose": pose, "length": max(len(pose.body.data), len(text) + 1)})

    return data


# TODO use dgs_types by default
def get_dataset(name="dicta_sign",
                poses="holistic",
                fps=25,
                split="train",
                components: List[str] = None,
                data_dir=None,
                max_seq_size=1000):
    print("Loading", name, "dataset...")
    data = get_tfds_dataset(name=name, poses=poses, fps=fps, split=split, components=components, data_dir=data_dir)

    data = [d for datum in data for d in process_datum(datum)]
    data = [d for d in data if d["length"] < max_seq_size]

    return TextPoseDataset(data)


def get_datasets(poses="holistic", fps=25, split="train", components: List[str] = None, max_seq_size=1000):
    dicta_sign = get_dataset(name="dicta_sign",
                             poses=poses,
                             fps=fps,
                             split=split,
                             components=components,
                             max_seq_size=max_seq_size)
    # dgs_types = get_dataset(name="dgs_types", poses=poses, fps=fps, split=split, components=components,
    #                         max_seq_size=max_seq_size)
    autsl = get_dataset(name="autsl",
                        poses=poses,
                        fps=fps,
                        split=split,
                        components=components,
                        max_seq_size=max_seq_size)

    all_data = dicta_sign.data + autsl.data
    return TextPoseDataset(all_data)

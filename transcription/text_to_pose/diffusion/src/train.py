import os

import pytorch_lightning as pl
from pytorch_lightning.callbacks import ModelCheckpoint
from pytorch_lightning.loggers import WandbLogger
from torch.utils.data import DataLoader

from _shared.collator import zero_pad_collator
from _shared.models import PoseEncoderModel
from _shared.tokenizers import HamNoSysTokenizer

from text_to_pose.diffusion.src.args import args
from .data import get_datasets, get_dataset
from text_to_pose.diffusion.src.model.iterative_decoder import IterativeGuidedPoseGenerationModel
from text_to_pose.diffusion.src.model.text_encoder import TextEncoderModel

if __name__ == '__main__':
    LOGGER = None
    if not args.no_wandb:
        LOGGER = WandbLogger(project="text-to-pose", log_model=False, offline=False)
        if LOGGER.experiment.sweep_id is None:
            LOGGER.log_hyperparams(args)

    train_dataset = get_datasets(poses=args.pose,
                                 fps=args.fps,
                                 components=args.pose_components,
                                 max_seq_size=args.max_seq_size,
                                 split="train[5:]")
    train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, collate_fn=zero_pad_collator)

    # validation_dataset = get_datasets(poses=args.pose,
    #                                   fps=args.fps,
    #                                   components=args.pose_components,
    #                                   max_seq_size=args.max_seq_size,
    #                                   split="train[:10]")

    validation_dataset = get_dataset(poses=args.pose,
                                     fps=args.fps,
                                     components=args.pose_components,
                                     max_seq_size=args.max_seq_size,
                                     split="train[:10]")
    validation_loader = DataLoader(validation_dataset, batch_size=args.batch_size, collate_fn=zero_pad_collator)

    # # TODO remove, this tests ovefitting
    # train_dataset = validation_dataset
    # train_loader = validation_loader

    _, num_pose_joints, num_pose_dims = train_dataset[0]["pose"]["data"].shape

    pose_encoder = PoseEncoderModel(pose_dims=(num_pose_joints, num_pose_dims),
                                    hidden_dim=args.hidden_dim,
                                    encoder_depth=args.pose_encoder_depth,
                                    encoder_heads=args.encoder_heads,
                                    encoder_dim_feedforward=args.encoder_dim_feedforward,
                                    max_seq_size=args.max_seq_size,
                                    dropout=0)

    text_encoder = TextEncoderModel(tokenizer=HamNoSysTokenizer(),
                                    max_seq_size=args.max_seq_size,
                                    hidden_dim=args.hidden_dim,
                                    num_layers=args.text_encoder_depth,
                                    dim_feedforward=args.encoder_dim_feedforward,
                                    encoder_heads=args.encoder_heads)

    # Model Arguments
    model_args = dict(pose_encoder=pose_encoder,
                      text_encoder=text_encoder,
                      hidden_dim=args.hidden_dim,
                      learning_rate=args.learning_rate,
                      seq_len_loss_weight=args.seq_len_loss_weight,
                      smoothness_loss_weight=args.smoothness_loss_weight,
                      noise_epsilon=args.noise_epsilon,
                      num_steps=args.num_steps)

    if args.checkpoint is not None:
        model = IterativeGuidedPoseGenerationModel.load_from_checkpoint(args.checkpoint, **model_args)
    else:
        model = IterativeGuidedPoseGenerationModel(**model_args)

    callbacks = []
    if LOGGER is not None:
        os.makedirs("models", exist_ok=True)

        callbacks.append(
            ModelCheckpoint(dirpath="models/" + LOGGER.experiment.name,
                            filename="model",
                            verbose=True,
                            save_top_k=1,
                            monitor='validation_dtw_mje',
                            mode='min'))

    trainer = pl.Trainer(max_epochs=5000,
                         logger=LOGGER,
                         callbacks=callbacks,
                         check_val_every_n_epoch=1,
                         accelerator='gpu',
                         devices=args.num_gpus)

    trainer.fit(model, train_dataloaders=train_loader, val_dataloaders=validation_loader)

# Diffusion

This is a non-autoregressive pose sequence generator. Starting from a bad pose sequence, we would like to iteratively
refine it, by predicting for each frame the desired change.

For pretraining, this model can learn to refine any pose sequence, regardless of the text input. 
In fine-tuning, the refinement process is conditioned on the text input.


## Training 

```bash
python -m text_to_pose.diffusion.src.train
```




-
-
-
-
-
-
-
-
-
-
-
-

#### Pseudo code:

```python
text_embedding = embed(text)
sequence_length = predict_length(text_embedding)
initial_pose_sequence = initial_frame.repeat(sequence_length)
for i in reversed(range(num_steps)):
    yield initial_pose_sequence
    refinement = predict_change(text_embedding, initial_pose_sequence)
    step_size = get_step_size(i)
    initial_pose_sequence += step_size * refinement
```

## Advantages:

1. Non-autoregressive, and therefore extremely fast (10 refinements, with batch size 32 in 0.15 seconds)
2. Controllable number of refinements - can try to refine the sequence in 1 step, or let it run for 1000
3. Controllable appearance - you control the appearance of the output by supplying the first pose
4. Composable - given multiple sequences to be generated and composed, use the last frame of each sequence to predict
   the next one
5. Consistent - always predicts all keypoints, including the hands
6. Can be used to correct a pose sequence with missing frames/keypoints


## Extra details

- Model tests, including overfitting, and continuous integration
- We remove the legs because they are not informative
- For experiment management we use WANDB
- Training works on CPU and GPU (90% util)
- Multiple-GPUs not tested



Instead of predicting the noise as formulated by Ho et al. (2020) `Jonathan Ho, Ajay Jain, and Pieter Abbeel. Denoising diffusion probabilistic models. Advances in
Neural Information Processing Systems, 33:6840–6851, 2020.`,
we follow Ramesh et al. (2022) `Aditya Ramesh, Prafulla Dhariwal, Alex Nichol, Casey Chu, and Mark Chen. Hierarchical textconditional image generation with clip latents. arXiv preprint arXiv:2204.06125, 2022.`
and predict the signal itself, i.e., `xˆ0 = G(xt, t, c)`.

## Inference types

In every time step `t` we predict the clean sample `x_0 = Model(x_t, t, c)` and noise it back to `x_{t−1}`.

Normal

Or

Guidance free
```
unconditional = Model(x_t, t, ∅)
conditional = Model(x_t, t, c)
Model_f(x_t, t, c) = unconditional + s * (conditional - unconditional)
```

## Example

Given the following never-seen HamNoSys text sequence:

![](assets/example/494_GSL_text.png)

We predict the number of frames to generate (77) which is close to the reference number (66).

We use the first reference frame, expanded 77 times as a starting sequence to be refined iteratively.

|                | Reference                                        | Predicted                                                                                           | Predicted                                                                                          |
|----------------|--------------------------------------------------|-----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| Frames         | 66                                               | 77                                                                                                  | 77                                                                                                 |
| Starting Frame | N/A                                              | From [494_GSL](https://www.sign-lang.uni-hamburg.de/dicta-sign/portal/concepts/gsl/494.mp4) | From [118_LSF](https://www.sign-lang.uni-hamburg.de/dicta-sign/portal/concepts/lsf/118.mp4) |
| Pose           | ![original](assets/example/494_GSL_original.gif) | ![pred](assets/example/494_GSL_pred.gif)                                                            | ![other](assets/example/494_GSL_other.gif)                                                         |

With the following [training](https://wandb.ai/amit_my/text-to-pose/runs/392fs203) loss curve:

![loss](assets/loss.png)
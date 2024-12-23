# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

# This source code is licensed under the license found in the
# LICENSE file in the root directory of this source tree.

from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

from utils.common_config import (
    get_test_dataset,
    get_test_transform,
)


def compute_eval_metrics(
    counterfactuals,
    dataset,
):
    #This need to be adapted so that I can also measure a same kp across experiments
    """
    Compute eval metrics from the paper `Counterfactual Visual Explanations`.

    We compute the Near-KP and Same-KP metric using the keypoint annotations
    from the dataset. In particular, for each cell replacement, we find what
    keypoints are present in the cell from the query and distractor image(s).
    If there are keypoints present, we increment the Near-KP score, which means
    we are replacing regions near important object parts. If the cell in the
    query image and the cell in the distractor image have at least one keypoint
    in common we increase the Same-KP metric. This means we are replacing
    semantically consistent parts. We track the metrics on a sample-wise level,
    and average the results when reporting numbers in the paper.

    Results are returned as a dictionary.
    """

    counterfactuals_inital = np.load('./output/counterfactuals_ours_cub_vgg16/counterfactuals.npy', allow_pickle=True).item()

    # initialize results dict
    results = {
        "Same-KP": defaultdict(list),
    }

    # load keypoint annotations into memory once
    n_parts = len(dataset.parts_name_index)
    keypoints = torch.stack(
        [
            torch.from_numpy(dataset.__getitem__(index)["parts"])
            for index in range(len(dataset))
        ],
        dim=0,
    )  # n x n_parts x n_pix x n_pix (n_pix = 7)
    #Idk what that comment references but might be a shape thing I have to deal with...
    #but could also just be implicit and change when I adjust everything else... 

    # evaluate all counterfactuals
    for counterfactual, initial in zip(counterfactuals.values(), counterfactuals_inital.values()):
        # gather query and distractor indexes
        query_index = counterfactual["query_index"]
        initial_index = initial["query_index"]

        # gather keypoint annotations for query and distractor images
        # of shape (n x n_parts x n_pix x n_pix)
        query_keypoints = keypoints[query_index]
        initial_keypoints = keypoints[initial_index]
        if len(query_keypoints.shape) == 3:
            query_keypoints = query_keypoints.unsqueeze(0)
        if len(initial_keypoints.shape) == 3:
            initial_keypoints = initial_keypoints.unsqueeze(0)

        # flatten the keypoint maps
        query_keypoints = (
            torch.permute(query_keypoints, (1, 0, 2, 3)).reshape(n_parts, -1).float()
        )
        initial_keypoints = (
            torch.permute(initial_keypoints, (1, 0, 2, 3))
            .reshape(n_parts, -1)
            .float()
        )

        # measure near-kp and same-kp for each edit
        for edit, edit_initial in zip(counterfactual["edits"], initial["edits"]):
            query_cell, initial_cell = edit[0], edit_initial[0]
            same_kp = torch.any(
                torch.logical_and(
                    query_keypoints[:, query_cell],
                    initial_keypoints[:, initial_cell],
                )
            ).float()
            results["Same-KP"][query_index].append(same_kp.item())

    # average the results
    single_edit = {}
    all_edit = {}

    single_edit["Same-KP"] = np.nanmean([res[0] for res in results["Same-KP"].values()])

    all_edit["Same-KP"] = np.nanmean(
        np.concatenate(list(res for res in results["Same-KP"].values()))
    )

    # report results for single-edit and all edits
    results["single_edit"] = single_edit
    results["all_edit"] = all_edit

    return results

dataset = get_test_dataset(transform=get_test_transform())

path  = Path('./output/counterfactuals_ours_cub_vgg16/')
all_paths = list(path.iterdir())
for p in all_paths: 
    counterfactuals = np.load(p, allow_pickle=True).item()

    result = compute_eval_metrics(
        counterfactuals,
        dataset=dataset,
    )

    print(p)
    print("Eval results single edit: {}".format(result["single_edit"]))
    print("Eval results all edits: {}".format(result["all_edit"]))
    print('----------------------------------------')
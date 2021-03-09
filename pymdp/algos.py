import numpy as np

from pymdp import utils
from pymdp.maths import spm_norm, spm_log, spm_dot, softmax


def mmp(
    ll_seq,
    B,
    policy,
    prev_actions=None,
    prior=None,
    grad_descent=False,
    num_iter=10,
    tau=0.25,
    final_timestep=False,
):
    past_len = len(ll_seq)
    future_len = policy.shape[0]
    infer_len = (past_len + future_len - 1) if final_timestep else (past_len + future_len)
    future_cutoff = past_len + future_len - 2

    _, num_states, _, num_factors = utils.get_model_dimensions(B=B)
    B = utils.to_obj_array(B)

    qs_seq = utils.obj_array(infer_len)
    for t in range(infer_len):
        qs_seq[t] = utils.obj_array_uniform(num_states)

    qs_final = utils.obj_array_zeros(num_states)

    if prior is None:
        prior = utils.obj_array_uniform(num_states)

    trans_B = utils.obj_array(num_factors)

    for f in range(num_factors):
        trans_B[f] = spm_norm(np.swapaxes(B[f], 0, 1))

    if prev_actions is None:
        prev_actions = np.zeros((past_len, policy.shape[1]))
    policy = np.vstack((prev_actions, policy))

    vfe = 0.0
    for _ in range(num_iter):
        for t in range(infer_len):
            for f in range(num_factors):
                if t < past_len:
                    lnA = spm_log(spm_dot(ll_seq[t], qs_seq[t], [f]))
                else:
                    lnA = np.zeros(num_states[f])

                if t == 0:
                    lnB_past = spm_log(prior[f])
                else:
                    past_msg = B[f][:, :, int(policy[t - 1, f])].dot(qs_seq[t - 1][f])
                    lnB_past = spm_log(past_msg)

                if t >= future_cutoff:
                    lnB_future = qs_final[f]
                else:
                    future_msg = trans_B[f][:, :, int(policy[t, f])].dot(qs_seq[t + 1][f])
                    lnB_future = spm_log(future_msg)

                if grad_descent:
                    ln_qs = spm_log(qs_seq[t][f])
                    coeff = 1 if (t >= future_cutoff) else 2
                    err = (coeff * lnA + lnB_past + lnB_future) - coeff * ln_qs
                    err -= err.mean()
                    ln_qs = ln_qs + tau * err
                    qs_seq[t][f] = softmax(ln_qs)
                    
                    if (t == 0) or (t == (infer_len - 1)):
                        vfe = vfe + (0.5 * ln_qs.dot(0.5 * err))
                    else:
                        term = 0.5 * (err - (num_factors - 1) * lnA / num_factors)
                        vfe += ln_qs.dot(term)

                else:
                    qs_seq[t][f] = softmax(lnA + lnB_past + lnB_future)

    return qs_seq, vfe
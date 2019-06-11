""" Runs a Deep500 benchmark recipe.

    NOTE: Every parameter (except `metrics`, `epochs`, and `batch_size`) has
          two additional parameters, `<param>_args` and `<param>_kwargs`, for
          extra arguments and keyword arguments, respectively.

    Parameters:
        Level 0 and 1:
        - model: Deep Neural Network to load
        - executor: Graph Executor to use

        Level 2:
        Dataset:
        - dataset: Dataset to load
        - train_sampler: Sampler for examples in training dataset
        - validation_sampler: Sampler for examples in validation dataset

        Training:
        - epochs: Run Trainer for #epochs
        - batch_size: Minibatch size for training
        - optimizer: Optimizer to use

        General:
        - events: List of events to use during execution
"""

from typing import Any, Dict, List, Tuple
import deep500 as d5
import deep500.datasets as d5ds
import deep500.networks as d5nt


def run_recipe(fixed: Dict[str, Any],
               mutable: Dict[str, Any],
               metrics: List[Tuple[d5.TestMetric, Any]]) -> bool:
    """ Runs a Deep500 recipe (see file documentation). Returns True on success
        and False on failure, printing the unacceptable metrics. """

    # Argument validation
    if any(k in mutable for k in fixed.keys()):
        raise RuntimeError('Fixed and mutable components cannot overlap')

    # Create unified dictionary
    comps = dict(fixed, **mutable)

    # Add missing arguments and keyword arguments
    old_keys = list(comps.keys())
    for k in old_keys:
        if (k not in ['batch_size', 'epochs', 'events'] and
                not (k.endswith('_args') or k.endswith('_kwargs'))):
            if ('%s_args' % k) not in comps:
                comps['%s_args' % k] = tuple()
            if ('%s_kwargs' % k) not in comps:
                comps['%s_kwargs' % k] = {}

    ########################################################################
    # Obtain dataset metadata
    if 'dataset' not in comps:
        raise SyntaxError('Dataset must be specified in training recipe')

    loss_op = d5ds.dataset_loss(comps['dataset'])
    ds_shape = d5ds.dataset_shape(comps['dataset'])
    ds_classes, sample_shape = ds_shape[0], ds_shape[1:]

    # Construct network
    if 'model' not in comps:
        raise SyntaxError('Model must be specified in recipe')
    if 'batch_size' not in comps:
        raise SyntaxError('Batch size must be specified in training recipe')
    batch = comps['batch_size']

    network, input_node, output_node = \
        d5nt.create_model(comps['model'], batch, *comps['model_args'],
                          shape=sample_shape, **comps['model_kwargs'])

    # Add loss function to model
    network.add_operation(loss_op([output_node, 'label'], 'loss'))

    # Construct dataset
    train_set, validation_set = d5ds.load_dataset(
        comps['dataset'], input_node, 'label', *comps['dataset_args'],
        **comps['dataset_kwargs'])

    # Construct samplers
    if 'train_sampler' in comps:
        train_sampler = comps['train_sampler'](
            train_set, batch, *comps['train_sampler_args'],
            **comps['train_sampler_kwargs'])
    else:
        train_sampler = train_set

    if 'validation_sampler' in comps:
        validation_sampler = comps['validation_sampler'](
            validation_set, batch, *comps['validation_sampler_args'],
            **comps['validation_sampler_kwargs'])
    else:
        validation_sampler = validation_set

    # Construct executor
    if 'executor' not in comps:
        raise SyntaxError('Executor must be specified in recipe')
    executor = comps['executor'](network, *comps['executor_args'],
                                 **comps['executor_kwargs'])

    # Construct optimizer
    if 'optimizer' not in comps:
        raise SyntaxError('Optimizer must be specified in training recipe')
    optimizer = comps['optimizer'](executor, 'loss', *comps['optimizer_args'],
                                   **comps['optimizer_kwargs'])

    # Add total time to metrics
    metrics.append((d5.WallclockTime(reruns=0, avg_over=1), None))

    ########################################################################
    # Create trainer and run
    if 'epochs' not in comps:
        raise SyntaxError('Epochs must be specified in training recipe')
    if 'events' not in comps:
        comps['events'] = None
    results = d5.test_training(executor, train_sampler, validation_sampler,
                               optimizer, comps['epochs'], batch, output_node,
                               metrics=[m[0] for m in metrics],
                               events=comps['events'])

    # Verify results
    ok = True
    for (metric, acceptable), result in zip(metrics, results):
        if acceptable is not None:
            if result < acceptable:
                print('FAIL %s: %s (Acceptable: %s)' % (
                    type(metric).__name__, result, acceptable))
                ok = False

    if not ok:
        return False
    else:
        print('PASSED')
        return True

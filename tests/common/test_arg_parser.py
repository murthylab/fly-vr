from flyvr.common.build_arg_parser import parse_arguments


def test_arg_parser():
    _ = parse_arguments("--config demo_experiment_and_playlist.yml")


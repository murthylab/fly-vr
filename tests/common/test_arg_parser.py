from flyvr.common.build_arg_parser import parse_arguments


def test_arg_parser():
    opts, parser = parse_arguments("--config demo_experiment_and_playlist.yml", return_parser=True)
    assert isinstance(opts.analog_in_channels, dict)
    assert isinstance(opts.analog_out_channels, dict)


def test_arg_parser_aio():
    opts = parse_arguments("--config configs/upstairs.part.yml")
    assert len(opts.analog_in_channels) == 5
    assert len(opts.analog_out_channels) == 1

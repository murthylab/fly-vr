from flyvr.common.build_arg_parser import parse_arguments

def test_arg_parser():
    options = parse_arguments("--config tests/test_data/flyvr_test_config.txt")

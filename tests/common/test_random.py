import pytest

from flyvr.common import Randomizer


@pytest.mark.parametrize('repeat', (1, 3, 5))
def test_none(repeat):
    r = Randomizer(1, 2, 3, mode=Randomizer.MODE_NONE, repeat=repeat)
    ok = repeat * [1, 2, 3]
    assert [v for v in r.iter_items()] == ok


@pytest.mark.parametrize('repeat', (1, 3, 5))
def test_shuffle(repeat):
    r = Randomizer(1, 2, 3, mode=Randomizer.MODE_SHUFFLE, random_seed=0, repeat=repeat)
    ok = repeat * [3, 2, 1]
    assert [v for v in r.iter_items()] == ok


@pytest.mark.parametrize('repeat', (1, 3, 5))
def test_random_walk(repeat):
    r = Randomizer(1, 2, 3, mode=Randomizer.MODE_RANDOM_WALK, random_seed=12, repeat=repeat)
    dat = [v for v in r.iter_items()]
    assert len(dat) == (3 * repeat)

    if repeat == 1:
        assert dat == [3, 2, 2]
    elif repeat == 3:
        assert dat == [3, 2, 2, 3, 1, 1, 3, 2, 1]
    elif repeat == 5:
        assert dat == [3, 2, 2, 3, 1, 1, 3, 2, 1, 2, 2, 2, 3, 3, 3]
    else:
        raise NotImplementedError


@pytest.mark.parametrize('repeat', (1, 3, 5))
def test_random_walk_non_consecutive(repeat):
    r = Randomizer(1, 2, 3, mode=Randomizer.MODE_RANDOM_WALK_NON_CONSECUTIVE, random_seed=99, repeat=repeat)
    dat = [v for v in r.iter_items()]
    assert len(dat) == (3 * repeat)

    if repeat == 1:
        assert dat == [2, 1, 2]
    elif repeat == 3:
        assert dat == [2, 1, 2, 1, 3, 1, 2, 1, 2]
    elif repeat == 5:
        assert dat == [2, 1, 2, 1, 3, 1, 2, 1, 2, 3, 2, 1, 2, 3, 1]
    else:
        raise NotImplementedError


def test_repr():
    s = repr(Randomizer(1, 2, 3, mode=Randomizer.MODE_RANDOM_WALK_NON_CONSECUTIVE, random_seed=99))
    assert s == '<Randomizer([1, 2, 3],mode=random_walk_non_consecutive,repeat=1>'
    s = repr(Randomizer('looooooong', 'thing', 'asfadsf', 'werwe', 'dasdfasf', 'asfasdfasdf',
                        mode=Randomizer.MODE_RANDOM_WALK_NON_CONSECUTIVE, random_seed=99))
    assert s == '<Randomizer([looooooong, thing, [...]],mode=random_walk_non_consecutive,repeat=1>'

"""The introductory scenes must preserve the boarding limit and timetable effects."""
from tools.build_ch06_raptor import build_intro


def test_intro_walk_keeps_first_round_and_second_ride_waits():
    intro = build_intro()
    assert intro['stops'] == list('ABCDE')
    run = intro['runs'][0]
    walk, gate, next_round, result = run['scenes'][3:7]
    assert walk['round'] == gate['round'] == 1
    assert walk['times'][3:] == [29510, None]  # D 08:11:50, E still unreachable
    assert next_round['times'] == gate['times']  # Copy before the second boarding
    assert result['times'][4] == 30300  # E 08:25
    assert result['times'][2] == gate['times'][2] == 30000  # Keep the one-ride answer


def test_intro_later_start_misses_connection():
    intro = build_intro()
    early, late = intro['runs']
    assert intro['walk'] == 110
    assert early['scenes'][1]['departure'] == 28800
    assert late['scenes'][1]['departure'] == 30600
    assert late['scenes'][-1]['times'][2:] == [31800, 31310, None]
    assert late['scenes'][-1]['marked'] == []  # No improvement: stop the search
    assert late['scenes'][-1]['round'] == 2
    assert len(late['rounds']) == 3  # No fabricated third round after convergence


def test_intro_third_round_preserves_arrivals_and_stops():
    run = build_intro()['runs'][0]
    second, third_start, third_end = run['scenes'][6:]
    assert third_start['kind'] == 'round'
    assert third_end['kind'] == 'end'
    assert third_start['round'] == third_end['round'] == 3
    assert third_start['marked'] == [4]  # Only E improved in round 2
    assert third_start['times'] == third_end['times'] == second['times']
    assert third_end['marked'] == []
    assert run['rounds'][3] == run['rounds'][2]

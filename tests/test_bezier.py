from pdf_to_dwg.converters import approximate_cubic_bezier


def test_bezier_returns_expected_number_of_points():
    points = approximate_cubic_bezier((0.0, 0.0), (1.0, 2.0), (2.0, 3.0), (4.0, 0.0), segments=10)
    assert len(points) == 11
    assert points[0] == (0.0, 0.0)
    assert points[-1] == (4.0, 0.0)


def test_bezier_invalid_segments():
    try:
        approximate_cubic_bezier((0, 0), (1, 1), (2, 1), (3, 0), segments=0)
    except ValueError:
        pass
    else:  # pragma: no cover - defensive
        raise AssertionError("Expected ValueError for segments < 1")

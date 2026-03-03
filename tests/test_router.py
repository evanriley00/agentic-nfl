from app.router.rules import decide_route

def test_predict_routes_to_ml_tool():
    r = decide_route("predict Justin Jefferson vs CHI", [])
    assert r.route == "tool"
    assert r.tool_name == "wr_yards_predict"
    assert r.tool_args["defteam"] == "CHI"

def test_analyze_routes_to_auto():
    r = decide_route("analyze Justin Jefferson vs CHI", [])
    assert r.route == "tool"
    assert r.tool_name in ("analyze_wr_auto", "analyze_wr")

def test_calculate_routes_to_calculator():
    r = decide_route("calculate 2+2", [])
    assert r.route == "tool"
    assert r.tool_name == "calculator"

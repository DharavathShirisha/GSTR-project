from backend.gstr1_validator import default_difference_reason, normalize_pos_value


def test_place_of_supply_keeps_state_name():
	assert normalize_pos_value("36 Telangana") == "36-Telangana"
	assert normalize_pos_value("36-Telangana") == "36-Telangana"


def test_reason_defaults_from_difference_amount():
	assert default_difference_reason(49.99) == "Round off diff."
	assert default_difference_reason(-49.99) == "Round off diff."
	assert default_difference_reason(50) == "Discount"
	assert default_difference_reason(100) == "Discount"
	assert default_difference_reason(100.01) == "TCS"
	assert default_difference_reason(None) == "Discount"

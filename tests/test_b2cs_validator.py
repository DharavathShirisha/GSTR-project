import pandas as pd

from backend.b2cs_validator import validate_b2cs_dataframe


def test_b2cs_calculates_cgst_sgst_for_same_state_and_igst_for_different_state():
    source = pd.DataFrame(
        [
            ["OE", "36-Telangana", "3.00", "100000", "0.00", ""],
            ["OE", "27-Maharashtra", "18.00", "100000", "0.00", ""],
        ],
        columns=["Type", "Place Of Supply", "Rate", "Taxable Value", "Cess Amount", "E-Commerce GSTIN"],
    )

    result = validate_b2cs_dataframe(source, "36")

    assert result.loc[0, "Supply Type"] == "Intra-state"
    assert result.loc[0, "Calculated CGST"] == 1500
    assert result.loc[0, "Calculated SGST"] == 1500
    assert result.loc[0, "Calculated IGST"] == 0
    assert result.loc[1, "Supply Type"] == "Inter-state"
    assert result.loc[1, "Calculated CGST"] == 0
    assert result.loc[1, "Calculated SGST"] == 0
    assert result.loc[1, "Calculated IGST"] == 18000
    assert result.loc[1, "Error Type"] == "POS Error"
    assert result.loc[0, "Error Type"] == ""

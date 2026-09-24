
import streamlit as st

from pages.b2b import show_b2b
from pages.b2cl import show_b2cl


# ============================================================
# Page Configuration
# ============================================================

st.set_page_config(
    page_title="HAA GSTR-1 Validator",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# Session State
# ============================================================

if "selected_page" not in st.session_state:
    st.session_state["selected_page"] = "Dashboard"


# ============================================================
# Navigation Functions
# ============================================================

def go_to_dashboard():
    st.session_state["selected_page"] = "Dashboard"


def go_to_b2b():
    st.session_state["selected_page"] = "B2B Invoice"


def go_to_b2cl():
    st.session_state["selected_page"] = "B2CL Invoice"


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:

    st.title("HAA GSTR-1 Validator")

    st.markdown("---")

    st.button(
        "🏠  Dashboard",
        use_container_width=True,
        type=(
            "primary"
            if st.session_state["selected_page"] == "Dashboard"
            else "secondary"
        ),
        on_click=go_to_dashboard,
    )

    st.button(
        "📄  B2B Invoice",
        use_container_width=True,
        type=(
            "primary"
            if st.session_state["selected_page"] == "B2B Invoice"
            else "secondary"
        ),
        on_click=go_to_b2b,
    )

    st.button(
        "📄  B2CL Invoice",
        use_container_width=True,
        type=(
            "primary"
            if st.session_state["selected_page"] == "B2CL Invoice"
            else "secondary"
        ),
        on_click=go_to_b2cl,
    )


# ============================================================
# Dashboard
# ============================================================

def show_dashboard():

    st.title("HAA GSTR-1 Validator")

    if st.session_state.get("use_sample"):
        metrics = {
            "B2B": 120,
            "Valid B2B": 105,
            "B2CL": 80,
            "Valid B2CL": 73,
            "Errors": 22,
        }
        cols = st.columns(5)
        for column, (label, value) in zip(cols, metrics.items()):
            column.metric(label, value)

        st.dataframe(
            {
                "Module": ["B2B", "B2CL"],
                "Total Records": [120, 80],
                "Valid Records": [105, 73],
                "Error Records": [15, 7],
            },
            hide_index=True,
        )
        return

    st.markdown(
        """
        ### Welcome

        GSTR-1 validation system for checking invoice data
        before filing.
        """
    )

    st.markdown("---")

    st.subheader("Validation Modules")

    st.markdown(
        """
        Select a validation module from the navigation menu.

        **Available modules:**

        - **B2B Invoice** — Validate B2B invoice data, GSTIN,
          Place of Supply, tax calculations and invoice values.
        - **B2CL Invoice** — Validate B2CL invoice data and
          applicable GST rules.
        """
    )


# ============================================================
# Page Routing
# ============================================================

if st.session_state["selected_page"] == "Dashboard":

    show_dashboard()

elif st.session_state["selected_page"] == "B2B Invoice":

    show_b2b()

elif st.session_state["selected_page"] == "B2CL Invoice":

    show_b2cl()

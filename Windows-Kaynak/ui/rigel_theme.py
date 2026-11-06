"""RIGEL COST PRO görsel kabuğu — açık tema (beyaz/gri + mavi vurgu)."""

from __future__ import annotations

from ui.corporate_theme import font_family_css, stylesheet


def rigel_main_window_styles() -> str:
    ff = font_family_css()
    return stylesheet(
        f"""
        QMainWindow, #centralRoot, #bodyFrame, #contentStack {{
            background: #EEF2F6;
            {ff}
        }}
        #rigelQuickToolbar {{
            background: #F8FAFC;
            border: 0;
            border-bottom: 1px solid #CBD5E1;
            spacing: 2px;
            padding: 2px 6px;
        }}
        #rigelQuickToolbar QToolButton {{
            color: #1E3A5F;
            background: transparent;
            border: 0;
            border-radius: 3px;
            padding: 6px 10px;
            font-size: 13px;
            font-weight: 600;
            {ff}
        }}
        #rigelQuickToolbar QToolButton:hover {{
            background: #E2E8F0;
            color: #0B437C;
        }}
        #marketBar {{
            background: #FFFFFF;
            border-bottom: 1px solid #CBD5E1;
            max-height: 52px;
        }}
        #brandTitle {{
            color: #0B437C;
            font-size: 14px;
            font-weight: 800;
            letter-spacing: 0.2px;
        }}
        #brandSubtitle {{
            color: #667085;
            font-size: 10px;
        }}
        #marketCard {{
            background: #F8FAFC;
            border: 1px solid #D0D5DD;
            border-radius: 3px;
            min-width: 90px;
        }}
        #marketCardTitle {{
            color: #667085;
            font-size: 9px;
            font-weight: 600;
        }}
        #marketCardValue {{
            color: #101828;
            font-size: 12px;
            font-weight: 700;
        }}
        #marketDate {{
            color: #667085;
            font-size: 10px;
        }}
        #sideNavigation {{
            background: #F3F6FA;
            border-right: 1px solid #CBD5E1;
        }}
        #navScroll, #navMenuWidget,
        #navScroll > QWidget > QWidget {{
            background: #F3F6FA;
            border: 0;
        }}
        #departmentButton {{
            color: #C2410C;
            background: #FFF7ED;
            border: 1px solid #FED7AA;
            border-radius: 3px;
            padding: 5px 8px;
            font-weight: 800;
            text-align: left;
        }}
        #departmentButton:checked {{
            color: #FFFFFF;
            background: #0B437C;
            border-color: #0B437C;
        }}
        #departmentMenu {{
            background: transparent;
            border: 0;
        }}
        #navButton {{
            color: #344054;
            background: transparent;
            border: 0;
            border-radius: 3px;
            padding: 5px 10px 5px 14px;
            text-align: left;
            font-size: 12px;
            font-weight: 600;
        }}
        #navButton:hover {{
            background: #E8EEF5;
            color: #0B437C;
        }}
        #navButton:checked {{
            color: #FFFFFF;
            background: #2563EB;
            font-weight: 700;
        }}
        #authorCard {{
            background: #FFFFFF;
            border: 1px solid #D0D5DD;
            border-radius: 4px;
        }}
        #authorTitle {{
            color: #667085;
            font-size: 12px;
            font-weight: 700;
        }}
        #authorName {{
            color: #0B437C;
            font-size: 13px;
            font-weight: 800;
        }}
        QStatusBar {{
            background: #F8FAFC;
            color: #344054;
            border-top: 1px solid #CBD5E1;
            font-size: 13px;
            {ff}
        }}
        QStatusBar QLabel {{
            color: #344054;
            padding: 0 8px;
        }}
        """,
    )


def rigel_workflow_styles() -> str:
    ff = font_family_css()
    return stylesheet(
        f"""
        WorkflowPage {{
            background: #EEF2F6;
            color: #1F2937;
            {ff}
        }}
        WorkflowPage QLabel {{
            color: #374151;
            background: transparent;
        }}
        #rigelTabBar {{
            background: #E8EEF5;
            border-bottom: 1px solid #B7C7DB;
            padding: 2px 6px;
        }}
        #rigelTabTitle {{
            color: #0B437C;
            font-size: 12px;
            font-weight: 800;
            letter-spacing: 0.2px;
        }}
        #rigelGroupBar {{
            background: #F8FAFC;
            color: #667085;
            border: 1px solid #D0D5DD;
            border-radius: 0;
            padding: 2px 8px;
            font-size: 11px;
            font-style: italic;
            max-height: 22px;
        }}
        #workflowHeader, #workflowKpi, #workflowControls {{
            background: #FFFFFF;
            border: 1px solid #D0D5DD;
            border-radius: 0;
        }}
        #workflowDepartment {{ color: #667085; font-size: 9pt; font-weight: 700; }}
        #workflowModule {{ color: #0B437C; font-size: 11pt; font-weight: 800; }}
        #workflowDescription {{ color: #667085; font-size: 9pt; }}
        #workflowKpiTitle {{ color: #667085; font-size: 8.5pt; font-weight: 600; }}
        #workflowKpiValue {{ color: #1D4ED8; font-size: 10.5pt; font-weight: 800; }}
        #workflowKpi {{ max-height: 28px; }}
        #workflowFilters {{
            background: #F8FAFC;
            border: 1px solid #D0D5DD;
            max-height: 30px;
        }}
        #columnFilterBar {{
            background: #EEF2F7;
            border: 1px solid #BFCDE0;
            border-bottom: 0;
        }}
        #columnFilterInner {{
            background: #EEF2F7;
        }}
        #columnFilterBar QToolButton#columnFilterButton {{
            color: #101828;
            background: #FFFFFF;
            border: 1px solid #C5D0DE;
            border-radius: 0;
            padding: 1px 4px;
            font-size: 10.5pt;
            min-height: 22px;
            text-align: left;
        }}
        #columnFilterBar QToolButton#columnFilterButton[filterActive="true"] {{
            background: #DBEAFE;
            border-color: #3B82F6;
            color: #1E3A5F;
            font-weight: 700;
        }}
        #columnFilterPopup {{
            background: #FFFFFF;
            border: 1px solid #94A3B8;
        }}
        #columnFilterPopup QPushButton#filterPopupAction {{
            min-height: 24px;
            padding: 2px 8px;
            font-size: 10.5pt;
        }}
        #columnFilterPopup QPushButton#filterPopupApply {{
            min-height: 26px;
            background: #0B5A9C;
            color: #FFFFFF;
            border-color: #0B437C;
        }}
        #rigelFooter {{
            background: #EAF3FC;
            border-top: 1px solid #B7D1EC;
            color: #1E3A5F;
            font-size: 11px;
            font-weight: 600;
            max-height: 22px;
        }}
        QLineEdit {{
            color: #111827;
            background: #FFFFFF;
            border: 1px solid #BFCDE0;
            border-radius: 2px;
            padding: 3px 5px;
        }}
        QTableWidget, QTableView {{
            color: #111827;
            background: #FFFFFF;
            alternate-background-color: #F7FAFC;
            gridline-color: #D6DEE8;
            selection-background-color: #DCEBFA;
            selection-color: #0B437C;
            border: 1px solid #BFCDE0;
            font-size: 11pt;
        }}
        QHeaderView::section {{
            color: #FFFFFF;
            background: #0B437C;
            border: 1px solid #083562;
            padding: 4px 6px;
            font-weight: 700;
            font-size: 11pt;
        }}
        QPushButton {{
            color: #1E3A5F;
            background: #FFFFFF;
            border: 1px solid #B7C7DB;
            border-radius: 3px;
            min-height: 24px;
            padding: 1px 7px;
            font-weight: 700;
            font-size: 10.5pt;
        }}
        QPushButton:hover {{
            background: #F0F7FF;
            border-color: #0B74BE;
        }}
        #workflowPrimary {{
            color: #FFFFFF;
            background: #16A34A;
            border-color: #15803D;
        }}
        #workflowSecondary {{
            color: #FFFFFF;
            background: #0B5A9C;
            border-color: #0B437C;
        }}
        #workflowDanger {{
            color: #FFFFFF;
            background: #DC2626;
            border-color: #B91C1C;
        }}
        #workflowStatus {{
            color: #1E40AF;
            background: #DBEAFE;
            border: 1px solid #93C5FD;
            border-radius: 2px;
            padding: 2px 6px;
            font-size: 10pt;
            max-height: 22px;
        }}
        """,
    )

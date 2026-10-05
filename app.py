import csv
import math
import os

import pandas as pd
import streamlit as st


DATA_FILE = "attendance_records.csv"
REQUIRED_COLUMNS = [
    "Student Name",
    "Subject",
    "Classes Held",
    "Classes Attended",
    "Attendance %",
    "Status",
]


def empty_records():
    return pd.DataFrame(columns=REQUIRED_COLUMNS)


def load_records():
    """Read, validate, and clean the local attendance CSV file."""
    if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
        return empty_records()

    try:
        records = pd.read_csv(DATA_FILE)
    except (
        OSError,
        UnicodeDecodeError,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
    ):
        st.error("The saved attendance file could not be read.")
        return empty_records()

    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in records.columns
    ]
    if missing_columns:
        st.error("The saved attendance file is missing required columns.")
        return empty_records()

    records = records[REQUIRED_COLUMNS].copy()
    records["Student Name"] = (
        records["Student Name"].fillna("").astype(str).str.strip()
    )
    records["Subject"] = records["Subject"].fillna("").astype(str).str.strip()

    for column in ["Classes Held", "Classes Attended"]:
        records[column] = pd.to_numeric(records[column], errors="coerce")

    records = records.dropna(subset=["Classes Held", "Classes Attended"])
    records = records[
        (records["Student Name"] != "")
        & (records["Subject"] != "")
        & (records["Classes Held"] > 0)
        & (records["Classes Attended"] >= 0)
        & (records["Classes Attended"] <= records["Classes Held"])
    ]

    records["Classes Held"] = records["Classes Held"].astype(int)
    records["Classes Attended"] = records["Classes Attended"].astype(int)
    records["Attendance %"] = (
        records["Classes Attended"] / records["Classes Held"] * 100
    ).round(2)

    return records.reset_index(drop=True)


def save_record(student_name, subject_name, classes_held, classes_attended, target):
    """Save one checked record to the local CSV file."""
    attendance = round((classes_attended / classes_held) * 100, 2)
    status = "Safe" if attendance >= target else "Shortage"
    is_new_file = not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0

    with open(DATA_FILE, "a", newline="", encoding="utf-8") as attendance_file:
        writer = csv.DictWriter(attendance_file, fieldnames=REQUIRED_COLUMNS)
        if is_new_file:
            writer.writeheader()
        writer.writerow(
            {
                "Student Name": student_name,
                "Subject": subject_name,
                "Classes Held": classes_held,
                "Classes Attended": classes_attended,
                "Attendance %": attendance,
                "Status": status,
            }
        )


def extra_classes_needed(classes_held, classes_attended, target):
    """Calculate classes that must be attended consecutively to reach a target."""
    target_fraction = target / 100
    if classes_attended / classes_held >= target_fraction:
        return 0

    required = (target_fraction * classes_held - classes_attended) / (
        1 - target_fraction
    )
    return max(0, math.ceil(required))


st.set_page_config(
    page_title="Attendance Shortage Finder",
    page_icon="🎓",
    layout="wide",
)

st.title("🎓 College Attendance Shortage Finder")
st.caption("Add, search, filter, and understand attendance records in one place.")

with st.sidebar:
    st.header("Settings")
    target_attendance = st.slider(
        "Required attendance (%)",
        min_value=50,
        max_value=95,
        value=75,
        step=5,
        help="Students below this percentage are marked as having a shortage.",
    )
    st.info("All data stays in the local attendance_records.csv file on this computer.")

with st.expander("Preview a college CSV file"):
    uploaded_file = st.file_uploader(
        "Choose a CSV file to preview",
        type=["csv"],
        help="Preview only. It will not replace your saved records.",
    )
    if uploaded_file is not None:
        try:
            uploaded_data = pd.read_csv(uploaded_file)
            st.success("File loaded for preview.")
            st.dataframe(uploaded_data, use_container_width=True)
        except (
            UnicodeDecodeError,
            pd.errors.EmptyDataError,
            pd.errors.ParserError,
        ):
            st.error("This file could not be read as a CSV file.")

st.subheader("Add a new attendance record")
with st.form("add_attendance_form", clear_on_submit=True):
    entry_column, class_column = st.columns([2, 1])
    with entry_column:
        student_name = st.text_input("Student name", placeholder="Example: Rishi")
        subject_name = st.text_input("Subject name", placeholder="Example: DBMS")
    with class_column:
        classes_held = st.number_input(
            "Total classes held", min_value=1, value=50, step=1
        )
        classes_attended = st.number_input(
            "Classes attended", min_value=0, value=0, step=1
        )

    submitted = st.form_submit_button("Save attendance record", type="primary")

if submitted:
    clean_student_name = student_name.strip()
    clean_subject_name = subject_name.strip()

    if not clean_student_name or not clean_subject_name:
        st.warning("Enter both a student name and a subject name.")
    elif classes_attended > classes_held:
        st.warning("Classes attended cannot be more than total classes held.")
    else:
        save_record(
            clean_student_name,
            clean_subject_name,
            int(classes_held),
            int(classes_attended),
            target_attendance,
        )
        st.success("Attendance record saved successfully.")

records = load_records()

if records.empty:
    st.info("No valid records yet. Add your first record with the form above.")
    st.stop()

records["Status"] = records["Attendance %"].apply(
    lambda attendance: "Safe" if attendance >= target_attendance else "Shortage"
)

student_count = records["Student Name"].nunique()
record_count = len(records)
shortage_records = records[records["Status"] == "Shortage"]
shortage_count = len(shortage_records)
average_attendance = records["Attendance %"].mean()

st.divider()
st.subheader("Attendance dashboard")
metric_one, metric_two, metric_three, metric_four = st.columns(4)
metric_one.metric("Total students", student_count)
metric_two.metric("Subject records", record_count)
metric_three.metric("Shortage records", shortage_count)
metric_four.metric("Average attendance", f"{average_attendance:.2f}%")

chart_column, table_column = st.columns(2)

with chart_column:
    st.subheader("Subject-wise shortage chart")
    if shortage_count:
        shortage_by_subject = (
            shortage_records.groupby("Subject").size().sort_values(ascending=False)
        )
        st.bar_chart(shortage_by_subject)
    else:
        st.success("No shortage records at the selected attendance target.")

with table_column:
    st.subheader("Attendance by subject")
    average_by_subject = (
        records.groupby("Subject")["Attendance %"]
        .mean()
        .sort_values(ascending=False)
    )
    st.bar_chart(average_by_subject)

st.divider()
st.subheader("Find a student")
student_options = ["All students"] + sorted(records["Student Name"].unique())
selected_student = st.selectbox("Choose a student", student_options)

if selected_student == "All students":
    visible_records = records
else:
    visible_records = records[records["Student Name"] == selected_student]

st.dataframe(visible_records, use_container_width=True, hide_index=True)

if selected_student != "All students":
    st.subheader("Smart attendance guide")
    selected_shortages = visible_records[visible_records["Status"] == "Shortage"].copy()

    if selected_shortages.empty:
        st.success(f"{selected_student} is safe in every saved subject.")
    else:
        selected_shortages["Classes needed to reach target"] = selected_shortages.apply(
            lambda row: extra_classes_needed(
                row["Classes Held"],
                row["Classes Attended"],
                target_attendance,
            ),
            axis=1,
        )
        st.info("These estimates assume the student attends every upcoming class.")
        st.dataframe(
            selected_shortages[
                [
                    "Subject",
                    "Attendance %",
                    "Classes needed to reach target",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )

st.divider()
st.subheader(f"Students below {target_attendance}% attendance")
if shortage_records.empty:
    st.success("No students are below the selected attendance target.")
else:
    st.dataframe(shortage_records, use_container_width=True, hide_index=True)

download_data = records.to_csv(index=False).encode("utf-8")
st.download_button(
    "Download attendance report",
    data=download_data,
    file_name="attendance_report.csv",
    mime="text/csv",
)

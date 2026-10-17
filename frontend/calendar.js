// ========================================
// AI Campus Assistant - Сарын календарь
// ========================================
// Даалгаврын дедлайнуудыг сарын хүснэгт дээр харуулна.
// Долоо хоног Даваа гарагаас эхэлнэ.

const MAX_ITEMS_PER_DAY = 3;

let calendarMonth = startOfMonth(new Date());
let selectedCalendarDate = todayIso();

const calendarGrid = document.getElementById("calendar-grid");
const calendarWeekdays = document.getElementById("calendar-weekdays");
const calendarMonthLabel = document.getElementById("calendar-month");
const calendarDetailTitle = document.getElementById("calendar-detail-title");
const calendarDetailList = document.getElementById("calendar-detail-list");

function startOfMonth(date) {
    return new Date(date.getFullYear(), date.getMonth(), 1);
}

function toIso(date) {
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${date.getFullYear()}-${month}-${day}`;
}

function addDays(date, days) {
    const copy = new Date(date);
    copy.setDate(copy.getDate() + days);
    return copy;
}

// Сарын хүснэгтийн эхний нүд: тухайн сарын 1-ний өмнөх Даваа гараг
function calendarStartDate(month) {
    const mondayOffset = (month.getDay() + 6) % 7;
    return addDays(month, -mondayOffset);
}

// Огноо бүрээр бүлэглэсэн даалгаврууд
function groupAssignmentsByDate() {
    const groups = {};

    sortAssignments(assignments, "deadline").forEach(item => {
        if (!groups[item.deadline]) {
            groups[item.deadline] = [];
        }
        groups[item.deadline].push(item);
    });

    return groups;
}

function renderWeekdays() {
    calendarWeekdays.replaceChildren();
    // 2024-01-01 бол Даваа гараг
    for (let index = 0; index < 7; index += 1) {
        const cell = document.createElement("div");
        cell.textContent = formatDateObject(new Date(2024, 0, 1 + index), { weekday: "short" });
        calendarWeekdays.appendChild(cell);
    }
}

function createCalendarPill(item) {
    const pill = document.createElement("span");
    pill.className = "calendar-pill";
    pill.classList.toggle("completed", item.completed);
    pill.style.borderLeftColor = item.course_color || "#94a3b8";
    pill.textContent = item.title;
    return pill;
}

function createDayCell(date, groups) {
    const iso = toIso(date);
    const items = groups[iso] || [];

    const cell = document.createElement("button");
    cell.type = "button";
    cell.className = "calendar-day";
    cell.setAttribute("role", "gridcell");
    cell.dataset.date = iso;

    if (date.getMonth() !== calendarMonth.getMonth()) {
        cell.classList.add("outside-month");
    }
    if (iso === todayIso()) {
        cell.classList.add("today");
    }
    if (iso === selectedCalendarDate) {
        cell.classList.add("selected");
        cell.setAttribute("aria-selected", "true");
    }
    if (items.some(item => !item.completed && daysUntil(item.deadline) < 0)) {
        cell.classList.add("has-overdue");
    }

    const label = formatDate(iso, { month: "long", day: "numeric", weekday: "long" });
    cell.setAttribute(
        "aria-label",
        items.length ? `${label}, ${t("stats.items", { n: items.length })}` : label
    );

    const number = document.createElement("span");
    number.className = "calendar-day-number";
    number.textContent = date.getDate();
    cell.appendChild(number);

    items.slice(0, MAX_ITEMS_PER_DAY).forEach(item => cell.appendChild(createCalendarPill(item)));

    if (items.length > MAX_ITEMS_PER_DAY) {
        const more = document.createElement("span");
        more.className = "calendar-more";
        more.textContent = t("calendar.more", { n: items.length - MAX_ITEMS_PER_DAY });
        cell.appendChild(more);
    }

    cell.addEventListener("click", () => {
        selectedCalendarDate = iso;
        renderCalendar();
    });

    return cell;
}

function renderCalendarDetail(groups) {
    const items = groups[selectedCalendarDate] || [];

    calendarDetailTitle.textContent = t("calendar.selected", {
        date: formatDate(selectedCalendarDate, { year: "numeric", month: "long", day: "numeric" })
    });
    calendarDetailList.replaceChildren();

    if (items.length === 0) {
        const empty = document.createElement("li");
        empty.className = "empty-message";
        empty.textContent = t("calendar.noItems");
        calendarDetailList.appendChild(empty);
        return;
    }

    items.forEach(item => {
        const row = document.createElement("li");
        row.className = `calendar-detail-item ${dueState(item)}`;

        const title = document.createElement("strong");
        title.textContent = item.title;

        const status = document.createElement("span");
        status.className = "calendar-detail-status";
        status.textContent = dueLabel(item);

        row.append(
            createCourseChip(item.course, item.course_color),
            title,
            createPriorityBadge(item.priority),
            status
        );
        calendarDetailList.appendChild(row);
    });
}

function renderCalendar() {
    const groups = groupAssignmentsByDate();

    calendarMonthLabel.textContent = formatDateObject(calendarMonth, {
        year: "numeric",
        month: "long"
    });

    renderWeekdays();
    calendarGrid.replaceChildren();

    // 6 долоо хоног × 7 өдөр = 42 нүд (ямар ч сар багтана)
    const start = calendarStartDate(calendarMonth);
    for (let index = 0; index < 42; index += 1) {
        calendarGrid.appendChild(createDayCell(addDays(start, index), groups));
    }

    renderCalendarDetail(groups);
}

function moveCalendar(months) {
    calendarMonth = new Date(calendarMonth.getFullYear(), calendarMonth.getMonth() + months, 1);
    renderCalendar();
}

document.getElementById("calendar-prev").addEventListener("click", () => moveCalendar(-1));
document.getElementById("calendar-next").addEventListener("click", () => moveCalendar(1));
document.getElementById("calendar-today").addEventListener("click", () => {
    calendarMonth = startOfMonth(new Date());
    selectedCalendarDate = todayIso();
    renderCalendar();
});

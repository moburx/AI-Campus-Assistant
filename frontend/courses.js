// ========================================
// AI Campus Assistant - Хичээл удирдах хэсэг
// ========================================

let courses = [];

const courseForm = document.getElementById("course-form");
const courseNameInput = document.getElementById("course-name");
const courseColorInput = document.getElementById("course-color");
const courseList = document.getElementById("course-list");
const courseMessage = document.getElementById("course-message");
const courseOptions = document.getElementById("course-options");

async function loadCourses() {
    courses = await apiJson("/courses", {}, "courses.saveFailed");
}

function resetCourses() {
    courses = [];
    courseMessage.textContent = "";
}

function showCourseMessage(text) {
    courseMessage.textContent = text;
}

// Даалгавар нэмэх/засах формын автоматаар гүйцээх жагсаалт
function renderCourseOptions() {
    courseOptions.replaceChildren();

    courses.forEach(course => {
        const option = document.createElement("option");
        option.value = course.name;
        courseOptions.appendChild(option);
    });
}

// Даалгаврын жагсаалтын "Бүх хичээл" шүүлтүүр
function renderCourseFilter() {
    const previous = courseFilter.value;
    courseFilter.replaceChildren();

    const allOption = document.createElement("option");
    allOption.value = "all";
    allOption.textContent = t("filter.allCourses");
    courseFilter.appendChild(allOption);

    courses.forEach(course => {
        const option = document.createElement("option");
        option.value = String(course.id);
        option.textContent = course.name;
        courseFilter.appendChild(option);
    });

    // Сонгосон хичээл устсан бол "Бүх хичээл" рүү буцна.
    const stillExists = [...courseFilter.options].some(option => option.value === previous);
    courseFilter.value = stillExists ? previous : "all";
}

function createProgressBar(done, total, color) {
    const track = document.createElement("div");
    track.className = "progress-track";
    track.setAttribute("role", "progressbar");
    track.setAttribute("aria-valuemin", "0");
    track.setAttribute("aria-valuemax", String(total));
    track.setAttribute("aria-valuenow", String(done));

    const fill = document.createElement("div");
    fill.className = "progress-fill";
    fill.style.width = total ? `${Math.round((done / total) * 100)}%` : "0%";
    fill.style.backgroundColor = color;

    track.appendChild(fill);
    return track;
}

function createCourseItem(course) {
    const item = document.createElement("li");
    item.className = "course-item";

    const colorInput = document.createElement("input");
    colorInput.type = "color";
    colorInput.value = course.color;
    colorInput.className = "course-color-input";
    colorInput.title = t("courses.color");
    colorInput.setAttribute("aria-label", `${t("courses.color")}: ${course.name}`);
    colorInput.addEventListener("change", () => updateCourse(course.id, { color: colorInput.value }));

    const info = document.createElement("div");
    info.className = "course-info";

    const name = document.createElement("strong");
    name.textContent = course.name;

    const count = document.createElement("span");
    count.className = "course-count";
    count.textContent = t("courses.count", { done: course.completed, total: course.total });

    info.append(name, count, createProgressBar(course.completed, course.total, course.color));

    const actions = document.createElement("div");
    actions.className = "course-actions";

    const renameButton = document.createElement("button");
    renameButton.type = "button";
    renameButton.className = "secondary-button";
    renameButton.textContent = t("courses.rename");
    renameButton.addEventListener("click", () => renameCourse(course));

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "delete-button";
    deleteButton.textContent = t("courses.delete");
    // Даалгавартай хичээлийг устгах боломжгүй.
    deleteButton.disabled = course.total > 0;
    deleteButton.title = course.total > 0 ? t("courses.hasAssignments") : "";
    deleteButton.addEventListener("click", () => deleteCourse(course));

    actions.append(renameButton, deleteButton);
    item.append(colorInput, info, actions);
    return item;
}

function renderCourses() {
    renderCourseOptions();
    renderCourseFilter();
    courseList.replaceChildren();

    if (courses.length === 0) {
        const empty = document.createElement("li");
        empty.className = "empty-message";
        empty.textContent = t("courses.empty");
        courseList.appendChild(empty);
        return;
    }

    courses.forEach(course => courseList.appendChild(createCourseItem(course)));
}

async function updateCourse(id, changes) {
    try {
        await apiJson(`/courses/${id}`, {
            method: "PATCH",
            body: JSON.stringify(changes)
        }, "courses.saveFailed");

        showCourseMessage("");
        // Хичээлийн нэр, өнгө даалгавар, календарь, статистикт ч харагдана.
        await refreshData();
    } catch (error) {
        console.error(error);
        showCourseMessage(error.message);
        renderCourses();
    }
}

function renameCourse(course) {
    const newName = prompt(t("courses.renamePrompt"), course.name);

    if (newName === null) return;

    const trimmed = newName.trim();
    if (!trimmed || trimmed === course.name) return;

    updateCourse(course.id, { name: trimmed });
}

async function deleteCourse(course) {
    if (!confirm(t("courses.confirmDelete"))) return;

    try {
        await apiJson(`/courses/${course.id}`, { method: "DELETE" }, "courses.saveFailed");
        showCourseMessage("");
        await refreshData();
    } catch (error) {
        console.error(error);
        showCourseMessage(error.message);
    }
}

courseForm.addEventListener("submit", async event => {
    event.preventDefault();

    const name = courseNameInput.value.trim();
    if (!name) return;

    try {
        await apiJson("/courses", {
            method: "POST",
            body: JSON.stringify({ name, color: courseColorInput.value })
        }, "courses.saveFailed");

        courseForm.reset();
        showCourseMessage("");
        await refreshData();
    } catch (error) {
        console.error(error);
        showCourseMessage(error.message);
    }
});

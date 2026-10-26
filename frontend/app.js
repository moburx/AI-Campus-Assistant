// ========================================
// AI Campus Assistant - Frontend (нийтлэг хэсэг)
// ========================================
// FastAPI өөрөө frontend-ийг үйлчилж байвал ижил origin тул "/api".
// Ингэснээр утаснаас http://192.168.x.x:8001 гэж нээсэн ч ажиллана.
// Зөвхөн Live Server (5500) эсвэл файлаар шууд нээсэн үед backend-ийн бүтэн хаягийг ашиглана.
const BACKEND_ORIGIN = "http://127.0.0.1:8001";
const LIVE_SERVER_PORT = "5500";
const SERVED_BY_BACKEND = window.location.protocol.startsWith("http")
    && window.location.port !== LIVE_SERVER_PORT;
const API_BASE = SERVED_BY_BACKEND ? "/api" : `${BACKEND_ORIGIN}/api`;
const TOKEN_KEY = "campus_token";
const USER_KEY = "campus_user";

const PRIORITY_ORDER = { high: 0, medium: 1, low: 2 };

let assignments = [];
let currentUser = null;

// ---------- Элементүүд ----------
const authSection = document.getElementById("auth-section");
const appContent = document.getElementById("app-content");
const mainNav = document.getElementById("main-nav");
const userInfo = document.getElementById("user-info");
const userNameLabel = document.getElementById("user-name");
const logoutButton = document.getElementById("logout-button");
const languageSelect = document.getElementById("language-select");
const welcomeGreeting = document.getElementById("welcome-greeting");

const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const registerLanguage = document.getElementById("register-language");
const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const authMessage = document.getElementById("auth-message");

const assignmentForm = document.getElementById("assignment-form");
const searchInput = document.getElementById("assignment-search");
const statusFilter = document.getElementById("assignment-status");
const courseFilter = document.getElementById("assignment-course-filter");
const priorityFilter = document.getElementById("assignment-priority-filter");
const sortSelect = document.getElementById("assignment-sort");

const editDialog = document.getElementById("edit-dialog");
const editForm = document.getElementById("edit-form");
const editMessage = document.getElementById("edit-message");
let editingAssignmentId = null;

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");
const chatInitialHTML = chatMessages.innerHTML;

// ---------- Token / session ----------
function getToken() {
    try {
        return localStorage.getItem(TOKEN_KEY);
    } catch (error) {
        return null;
    }
}

function saveSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function clearSession() {
    try {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
    } catch (error) {
        // localStorage ашиглах боломжгүй орчин
    }
}

// ---------- API туслах функцууд ----------
// Backend-ийн англи алдааны мессежийг сонгосон хэл рүү хөрвүүлнэ.
const ERROR_TRANSLATIONS = {
    "AI summary is not available right now.": "notices.aiUnavailable",
    "Could not summarize this notice.": "notices.summaryFailed",
    "AI daily limit reached.": "notices.aiQuota",
    "Username or email already exists.": "auth.userExists",
    "Invalid username or password.": "auth.invalidLogin",
    "A course with this name already exists.": "courses.exists",
    "This course still has assignments.": "courses.hasAssignments"
};

async function readError(response, fallbackKey) {
    try {
        const data = await response.json();

        if (typeof data.detail === "string") {
            const key = ERROR_TRANSLATIONS[data.detail];
            return key ? t(key) : data.detail;
        }

        if (Array.isArray(data.detail)) {
            return data.detail.map(item => item.msg).join(" ");
        }
    } catch (error) {
        // JSON биш хариу байж болно
    }

    return t(fallbackKey);
}

// Нэвтрээгүй хүсэлт (login, register)
async function publicPost(path, payload) {
    return fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
}

// JWT token-той хүсэлт
async function apiFetch(path, options = {}) {
    const headers = { ...(options.headers || {}) };

    if (options.body) {
        headers["Content-Type"] = "application/json";
    }

    const token = getToken();
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}${path}`, {
        ...options,
        headers
    });

    if (response.status === 401) {
        logout();
        showAuthMessage(t("auth.sessionExpired"));
        throw new Error(t("auth.sessionExpired"));
    }

    return response;
}

// JSON буцаадаг хүсэлт. Алдаа гарвал орчуулсан мессежтэй Error шиднэ.
async function apiJson(path, options = {}, fallbackKey = "common.error") {
    const response = await apiFetch(path, options);

    if (!response.ok) {
        throw new Error(await readError(response, fallbackKey));
    }

    return response.status === 204 ? null : response.json();
}

// ---------- Огноо ----------
function todayIso() {
    const now = new Date();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const day = String(now.getDate()).padStart(2, "0");
    return `${now.getFullYear()}-${month}-${day}`;
}

// Өнөөдрөөс хэдэн өдрийн дараа (сөрөг бол хэтэрсэн)
function daysUntil(isoDate) {
    const today = new Date(`${todayIso()}T00:00:00`);
    const target = new Date(`${isoDate}T00:00:00`);
    return Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

function dueLabel(item) {
    if (item.completed) {
        return t("due.done");
    }

    const days = daysUntil(item.deadline);

    if (Number.isNaN(days)) return "";
    if (days < 0) return t("due.overdue", { n: -days });
    if (days === 0) return t("due.today");
    return t("due.left", { n: days });
}

function dueState(item) {
    if (item.completed) return "completed";

    const days = daysUntil(item.deadline);
    if (days < 0) return "overdue";
    if (days <= 3) return "due-soon";
    return "upcoming";
}

// ---------- Нэвтрэх хэсгийн UI ----------
function showAuthMessage(text, isError = true) {
    authMessage.textContent = text;
    authMessage.className = isError ? "auth-message error" : "auth-message success";
}

function switchTab(tab) {
    const isLogin = tab === "login";

    loginForm.hidden = !isLogin;
    registerForm.hidden = isLogin;
    tabLogin.classList.toggle("active", isLogin);
    tabRegister.classList.toggle("active", !isLogin);
    authMessage.textContent = "";
}

// Утасны браузерын дээд/доод хэсгийг хуудасны өнгөтэй тааруулна.
const themeColorMeta = document.getElementById("theme-color");
const THEME_COLORS = { auth: "#5b3df0", light: "#f5f7fb", dark: "#141233" };

function setThemeColor(mode) {
    if (!themeColorMeta) return;

    if (mode === "auth") {
        themeColorMeta.content = THEME_COLORS.auth;
    } else {
        themeColorMeta.content = document.documentElement.dataset.theme === "dark"
            ? THEME_COLORS.dark
            : THEME_COLORS.light;
    }
}

function showAuth() {
    setThemeColor("auth");
    authSection.hidden = false;
    appContent.hidden = true;
    mainNav.hidden = true;
    userInfo.hidden = true;
    registerLanguage.value = currentLanguage;
}

function renderGreeting() {
    if (currentUser) {
        welcomeGreeting.textContent = t(greetingKey(), { name: currentUser.username });
    }
}

function showApp(user) {
    currentUser = user;
    setThemeColor("app");
    authSection.hidden = true;
    appContent.hidden = false;
    mainNav.hidden = false;
    userInfo.hidden = false;
    userNameLabel.textContent = user.username;

    // Хэрэглэгчийн хадгалсан хэлээр UI-г харуулна.
    if (user.preferred_language && user.preferred_language !== currentLanguage) {
        setLanguage(user.preferred_language);
        languageSelect.value = currentLanguage;
    }

    renderGreeting();
}

function logout() {
    chatSession += 1;
    clearSession();
    currentUser = null;
    assignments = [];
    resetCourses();
    resetStats();
    resetNotices();
    renderAll();
    chatMessages.innerHTML = chatInitialHTML;
    applyTranslations(chatMessages);
    chatSubmitButton.disabled = false;
    searchInput.value = "";
    statusFilter.value = "all";
    courseFilter.value = "all";
    priorityFilter.value = "all";

    if (editDialog.open) {
        editDialog.close();
    }

    closeAssistant({ restoreFocus: false });
    resetView();
    showAuth();
}

tabLogin.addEventListener("click", () => switchTab("login"));
tabRegister.addEventListener("click", () => switchTab("register"));
logoutButton.addEventListener("click", logout);

async function loginUser(username, password) {
    const response = await publicPost("/auth/login", { username, password });

    if (!response.ok) {
        throw new Error(await readError(response, "auth.loginFailed"));
    }

    const data = await response.json();
    saveSession(data.access_token, data.user);
    showApp(data.user);
    await refreshData();
    refreshNoticesIfStale();
}

loginForm.addEventListener("submit", async event => {
    event.preventDefault();

    const username = document.getElementById("login-username").value.trim();
    const password = document.getElementById("login-password").value;

    try {
        await loginUser(username, password);
        loginForm.reset();
        authMessage.textContent = "";
    } catch (error) {
        showAuthMessage(error.message);
    }
});

registerForm.addEventListener("submit", async event => {
    event.preventDefault();

    const payload = {
        username: document.getElementById("register-username").value.trim(),
        email: document.getElementById("register-email").value.trim(),
        password: document.getElementById("register-password").value,
        country: document.getElementById("register-country").value.trim() || "Other",
        preferred_language: registerLanguage.value
    };

    try {
        const response = await publicPost("/auth/register", payload);

        if (!response.ok) {
            throw new Error(await readError(response, "auth.registerFailed"));
        }

        // Бүртгүүлсний дараа автоматаар нэвтрүүлнэ
        await loginUser(payload.username, payload.password);
        registerForm.reset();
        authMessage.textContent = "";
    } catch (error) {
        showAuthMessage(error.message);
    }
});

// ---------- Хэл солих ----------
languageSelect.addEventListener("change", async () => {
    setLanguage(languageSelect.value);

    if (!currentUser || !getToken()) {
        return;
    }

    // Нэвтэрсэн бол сонголтыг профайлд хадгална (AI хариу ч энэ хэлээр гарна).
    try {
        currentUser = await apiJson("/auth/me", {
            method: "PATCH",
            body: JSON.stringify({ preferred_language: currentLanguage })
        });
        localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
    } catch (error) {
        console.error("Хэл хадгалж чадсангүй:", error);
    }
});

// Хэл солигдоход JS-ээр зурсан бүх хэсгийг дахин зурна.
document.addEventListener("languagechange", () => {
    languageSelect.value = currentLanguage;
    renderGreeting();
    renderAll();
});

// ---------- Өгөгдөл ачаалах ----------
async function loadAssignments() {
    assignments = await apiJson("/assignments", {}, "assign.loadFailed");
}

// Даалгавар, хичээл, статистикийг зэрэг ачаалаад бүгдийг зурна.
async function refreshData() {
    try {
        await Promise.all([loadAssignments(), loadCourses(), loadStats(), loadNotices()]);
    } catch (error) {
        console.error("API алдаа:", error);
        if (getToken()) {
            alert(t("assign.loadFailed"));
        }
    }

    renderAll();
}

function renderAll() {
    renderHome();
    renderNotices();
    renderAssignments();
    renderCourses();
    renderCalendar();
    renderStats();
}

// ---------- Даалгавар ----------
async function addAssignment(payload) {
    try {
        await apiJson("/assignments", {
            method: "POST",
            body: JSON.stringify(payload)
        }, "assign.saveFailed");

        await refreshData();
        return true;
    } catch (error) {
        console.error(error);
        alert(error.message);
        return false;
    }
}

async function updateAssignment(id, changes) {
    await apiJson(`/assignments/${id}`, {
        method: "PATCH",
        body: JSON.stringify(changes)
    }, "assign.saveFailed");

    await refreshData();
}

async function toggleAssignment(id) {
    const assignment = assignments.find(item => item.id === id);
    if (!assignment) return;

    try {
        await updateAssignment(id, { completed: !assignment.completed });
    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}

async function deleteAssignment(id) {
    if (!confirm(t("assign.confirmDelete"))) return;

    try {
        await apiJson(`/assignments/${id}`, { method: "DELETE" }, "assign.deleteFailed");
        await refreshData();
    } catch (error) {
        console.error(error);
        alert(error.message);
    }
}

function getFilteredAssignments() {
    const searchText = searchInput.value.trim().toLowerCase();
    const selectedStatus = statusFilter.value;
    const selectedCourse = courseFilter.value;
    const selectedPriority = priorityFilter.value;

    const filtered = assignments.filter(item => {
        const matchesSearch =
            item.title.toLowerCase().includes(searchText) ||
            item.course.toLowerCase().includes(searchText) ||
            (item.notes || "").toLowerCase().includes(searchText);

        const matchesStatus =
            selectedStatus === "all" ||
            (selectedStatus === "completed" && item.completed) ||
            (selectedStatus === "incomplete" && !item.completed);

        const matchesCourse =
            selectedCourse === "all" || String(item.course_id) === selectedCourse;

        const matchesPriority =
            selectedPriority === "all" || item.priority === selectedPriority;

        return matchesSearch && matchesStatus && matchesCourse && matchesPriority;
    });

    return sortAssignments(filtered, sortSelect.value);
}

function sortAssignments(list, mode) {
    const byDeadline = (a, b) => a.deadline.localeCompare(b.deadline);
    const byPriority = (a, b) =>
        (PRIORITY_ORDER[a.priority] ?? 1) - (PRIORITY_ORDER[b.priority] ?? 1);

    return [...list].sort((a, b) => {
        // Дууссан даалгаврууд үргэлж доор
        if (a.completed !== b.completed) {
            return a.completed ? 1 : -1;
        }

        if (mode === "newest") {
            return b.id - a.id;
        }

        if (mode === "priority") {
            return byPriority(a, b) || byDeadline(a, b);
        }

        return byDeadline(a, b) || byPriority(a, b);
    });
}

function createPriorityBadge(priority) {
    const badge = document.createElement("span");
    badge.className = `priority-badge priority-${priority}`;
    badge.textContent = t(`priority.${priority}`);
    return badge;
}

function createCourseChip(name, color) {
    const chip = document.createElement("span");
    chip.className = "course-chip";

    const dot = document.createElement("span");
    dot.className = "course-dot";
    dot.style.backgroundColor = color || "#94a3b8";

    chip.append(dot, document.createTextNode(name));
    return chip;
}

function createAssignmentElement(item) {
    const article = document.createElement("article");
    article.className = `assignment-item ${dueState(item)}`;
    article.dataset.id = item.id;

    const info = document.createElement("div");
    info.className = "assignment-info";

    const titleRow = document.createElement("div");
    titleRow.className = "assignment-title-row";

    const title = document.createElement("h3");
    title.textContent = item.title;
    titleRow.append(title, createPriorityBadge(item.priority));

    const meta = document.createElement("p");
    meta.className = "assignment-meta";

    const deadline = document.createElement("span");
    deadline.textContent = `${formatDate(item.deadline)} · ${dueLabel(item)}`;

    meta.append(createCourseChip(item.course, item.course_color), deadline);
    info.append(titleRow, meta);

    if (item.notes) {
        const notes = document.createElement("p");
        notes.className = "assignment-notes";
        notes.textContent = item.notes;
        info.appendChild(notes);
    }

    const actions = document.createElement("div");
    actions.className = "assignment-actions";

    const completeButton = document.createElement("button");
    completeButton.type = "button";
    completeButton.textContent = item.completed ? t("assign.undo") : t("assign.done");
    completeButton.addEventListener("click", () => toggleAssignment(item.id));

    const editButton = document.createElement("button");
    editButton.type = "button";
    editButton.className = "secondary-button";
    editButton.textContent = t("assign.edit");
    editButton.addEventListener("click", () => openEditDialog(item.id));

    const deleteButton = document.createElement("button");
    deleteButton.type = "button";
    deleteButton.className = "delete-button";
    deleteButton.textContent = t("assign.delete");
    deleteButton.addEventListener("click", () => deleteAssignment(item.id));

    actions.append(completeButton, editButton, deleteButton);
    article.append(info, actions);
    return article;
}

function renderAssignments() {
    const list = document.getElementById("assignment-list");
    const completed = assignments.filter(item => item.completed).length;

    document.getElementById("total-count").textContent = assignments.length;
    document.getElementById("completed-count").textContent = completed;
    document.getElementById("remaining-count").textContent = assignments.length - completed;

    list.replaceChildren();

    if (assignments.length === 0) {
        const message = document.createElement("p");
        message.className = "empty-message";
        message.textContent = t("assign.empty");
        list.appendChild(message);
        return;
    }

    const filtered = getFilteredAssignments();

    if (filtered.length === 0) {
        const message = document.createElement("p");
        message.className = "empty-message";
        message.textContent = t("assign.noMatch");
        list.appendChild(message);
        return;
    }

    filtered.forEach(item => list.appendChild(createAssignmentElement(item)));
}

assignmentForm.addEventListener("submit", async event => {
    event.preventDefault();

    const payload = {
        title: document.getElementById("assignment-title").value.trim(),
        course: document.getElementById("assignment-course").value.trim(),
        deadline: document.getElementById("assignment-deadline").value,
        priority: document.getElementById("assignment-priority").value,
        notes: document.getElementById("assignment-notes").value.trim()
    };

    if (!payload.title || !payload.course || !payload.deadline) {
        alert(t("assign.fillAll"));
        return;
    }

    if (await addAssignment(payload)) {
        assignmentForm.reset();
        document.getElementById("assignment-priority").value = "medium";
    }
});

[searchInput].forEach(element => element.addEventListener("input", renderAssignments));
[statusFilter, courseFilter, priorityFilter, sortSelect].forEach(element =>
    element.addEventListener("change", renderAssignments)
);

// ---------- Даалгавар засах цонх ----------
function openEditDialog(id) {
    const item = assignments.find(assignment => assignment.id === id);
    if (!item) return;

    editingAssignmentId = id;
    document.getElementById("edit-title").value = item.title;
    document.getElementById("edit-course").value = item.course;
    document.getElementById("edit-deadline").value = item.deadline;
    document.getElementById("edit-priority").value = item.priority;
    document.getElementById("edit-notes").value = item.notes || "";
    editMessage.textContent = "";

    editDialog.showModal();
    document.getElementById("edit-title").focus();
}

document.getElementById("edit-cancel").addEventListener("click", () => {
    editDialog.close();
});

editForm.addEventListener("submit", async event => {
    event.preventDefault();

    const changes = {
        title: document.getElementById("edit-title").value.trim(),
        course: document.getElementById("edit-course").value.trim(),
        deadline: document.getElementById("edit-deadline").value,
        priority: document.getElementById("edit-priority").value,
        notes: document.getElementById("edit-notes").value.trim()
    };

    if (!changes.title || !changes.course || !changes.deadline) {
        editMessage.textContent = t("assign.fillAll");
        return;
    }

    try {
        await updateAssignment(editingAssignmentId, changes);
        editDialog.close();
    } catch (error) {
        console.error(error);
        editMessage.textContent = error.message;
    }
});

editDialog.addEventListener("close", () => {
    editingAssignmentId = null;
});

// ---------- Чат ----------
// Гарах (logout) бүрд нэмэгдэнэ. Хариу ирэхээс өмнө хэрэглэгч гарсан бол
// хуучин хэрэглэгчийн хариуг шинэ хэрэглэгчид харуулахгүй.
let chatSession = 0;
const chatSubmitButton = chatForm.querySelector("button[type='submit']");

// "**тод**" хэсгийг <strong> болгоно. HTML-ийг шууд оруулахгүй (XSS-ээс хамгаална).
function appendInline(parent, text) {
    text.split("**").forEach((part, index) => {
        if (!part) return;
        if (index % 2 === 1) {
            const strong = document.createElement("strong");
            strong.textContent = part;
            parent.appendChild(strong);
        } else {
            parent.appendChild(document.createTextNode(part));
        }
    });
}

// AI-ийн markdown хариуг аюулгүй DOM болгож харуулна:
// "* " эсвэл "- " → жагсаалт, "1. " → дугаартай жагсаалт, бусад → догол мөр.
function renderMarkdown(container, markdown) {
    let currentList = null;
    let currentItem = null;

    markdown.split("\n").forEach(rawLine => {
        const line = rawLine.trim();

        if (!line) {
            currentList = null;
            currentItem = null;
            return;
        }

        const bullet = line.match(/^[*-]\s+(.*)$/);
        const numbered = line.match(/^\d+\.\s+(.*)$/);

        if (bullet || numbered) {
            const listTag = bullet ? "UL" : "OL";
            if (!currentList || currentList.tagName !== listTag) {
                currentList = document.createElement(listTag.toLowerCase());
                container.appendChild(currentList);
            }
            currentItem = document.createElement("li");
            appendInline(currentItem, (bullet || numbered)[1]);
            currentList.appendChild(currentItem);
            return;
        }

        // Жагсаалтын мөрийн дараах тайлбар мөр нь тухайн мөрийн хэсэг
        if (currentItem && /^\s{2,}/.test(rawLine)) {
            currentItem.appendChild(document.createElement("br"));
            appendInline(currentItem, line);
            return;
        }

        currentList = null;
        currentItem = null;
        const paragraph = document.createElement("p");
        appendInline(paragraph, line);
        container.appendChild(paragraph);
    });
}

// AI агентын хийсэн үйлдлүүдийг (нэмсэн, зассан, дуусгасан) жагсаалтаар харуулна.
function actionLabel(action) {
    if (!action.ok) {
        return { key: "action.failed", text: t("action.failed", { error: action.error || "" }) };
    }

    let key = "action.updated";
    if (action.tool === "add_assignment") {
        key = "action.added";
    } else if (action.changed && action.changed.length === 1 && action.changed[0] === "completed" && action.completed) {
        key = "action.completed";
    }

    return { key, text: t(key, { title: action.title }) };
}

function createActionList(actions) {
    const list = document.createElement("ul");
    list.className = "chat-actions";

    actions.forEach(action => {
        const item = document.createElement("li");
        const { key, text } = actionLabel(action);
        item.className = action.ok ? "chat-action" : "chat-action failed";
        item.dataset.kind = key;
        item.textContent = `${action.ok ? "✓" : "✕"} ${text}`;
        list.appendChild(item);
    });

    return list;
}

function addChatMessage(message, sender, source = null, actions = [], notice = null) {
    const element = document.createElement("div");
    element.classList.add("chat-message");
    element.classList.add(sender === "user" ? "user-message" : "bot-message");

    if (sender === "user") {
        element.textContent = message;
    } else {
        renderMarkdown(element, message);

        if (actions.length > 0) {
            element.appendChild(createActionList(actions));
        }

        // AI-ийн өдрийн хязгаар дууссан бол яагаад энгийн зөвлөмж гарсныг тайлбарлана.
        if (notice === "ai_quota") {
            const note = document.createElement("p");
            note.className = "chat-notice";
            note.dataset.i18n = "assistant.quotaNotice";
            note.textContent = t("assistant.quotaNotice");
            element.appendChild(note);
        }

        if (source) {
            const badge = document.createElement("span");
            badge.className = `chat-source chat-source-${source}`;
            badge.dataset.i18n = `source.${source}`;
            badge.textContent = t(`source.${source}`);
            element.appendChild(badge);
        }
    }

    chatMessages.appendChild(element);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return element;
}

// Сервертэй холбогдож чадахгүй үед ачаалсан даалгавраас товч тойм гаргана.
function generateOfflineAnswer() {
    const incomplete = sortAssignments(
        assignments.filter(task => !task.completed),
        "deadline"
    );

    const lines = [t("assistant.offline", { n: incomplete.length })];

    if (incomplete.length > 0) {
        lines.push(t("assistant.offlineNearest", {
            title: incomplete[0].title,
            date: formatDate(incomplete[0].deadline)
        }));
    }

    return lines.join("\n");
}

async function askAssistant(question) {
    return apiJson("/assistant", {
        method: "POST",
        body: JSON.stringify({ question })
    });
}

chatForm.addEventListener("submit", async event => {
    event.preventDefault();

    const question = chatInput.value.trim();
    if (!question || chatSubmitButton.disabled) return;

    addChatMessage(question, "user");
    chatInput.value = "";
    chatInput.focus();

    const session = chatSession;
    const pending = addChatMessage(t("assistant.thinking"), "bot");
    pending.classList.add("pending");
    chatSubmitButton.disabled = true;

    try {
        const data = await askAssistant(question);
        if (session !== chatSession) return; // хэрэглэгч гарсан
        pending.remove();

        const actions = data.actions || [];
        addChatMessage(data.answer, "bot", data.source, actions, data.notice);

        // AI даалгавар өөрчилсөн бол жагсаалт, календарь, статистикийг шинэчилнэ.
        if (actions.some(action => action.ok)) {
            await refreshData();
        }
    } catch (error) {
        if (session !== chatSession) return;
        console.error("Assistant алдаа:", error);
        pending.remove();
        // Нэвтрэх хугацаа дууссан бол apiFetch аль хэдийн logout хийсэн
        if (getToken()) {
            addChatMessage(generateOfflineAnswer(), "bot", "local");
        }
    } finally {
        if (session === chatSession) {
            chatSubmitButton.disabled = false;
        }
    }
});

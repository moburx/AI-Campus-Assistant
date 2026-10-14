const API_URL = "http://127.0.0.1:8000/api/assignments";

let assignments = [];

async function loadAssignments() {
    try {
        const response = await fetch(API_URL);

        if (!response.ok) {
            throw new Error("Даалгавар уншиж чадсангүй.");
        }

        assignments = await response.json();
        renderAssignments();
    } catch (error) {
        console.error("API алдаа:", error);
        alert("Сервертэй холбогдож чадсангүй. Backend ажиллаж байгаа эсэхийг шалгана уу.");
    }
}

async function addAssignment(title, course, deadline) {
    try {
        const response = await fetch(API_URL, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                title,
                course,
                deadline
            })
        });

        if (!response.ok) {
            throw new Error("Даалгавар нэмэхэд алдаа гарлаа.");
        }

        await loadAssignments();
    } catch (error) {
        console.error(error);
        alert("Даалгавар нэмэх боломжгүй байна.");
    }
}

async function toggleAssignment(id) {
    const assignment = assignments.find(
        item => item.id === id
    );

    if (!assignment) return;

    try {
        const response = await fetch(`${API_URL}/${id}`, {
            method: "PATCH",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                completed: !assignment.completed
            })
        });

        if (!response.ok) {
            throw new Error("Төлөв шинэчилж чадсангүй.");
        }

        await loadAssignments();
    } catch (error) {
        console.error(error);
        alert("Даалгаврын төлөв шинэчлэхэд алдаа гарлаа.");
    }
}

async function deleteAssignment(id) {
    const confirmed = confirm(
        "Энэ даалгаврыг устгах уу?"
    );

    if (!confirmed) return;

    try {
        const response = await fetch(`${API_URL}/${id}`, {
            method: "DELETE"
        });

        if (!response.ok) {
            throw new Error("Даалгавар устгаж чадсангүй.");
        }

        await loadAssignments();
    } catch (error) {
        console.error(error);
        alert("Даалгавар устгахад алдаа гарлаа.");
    }
}

function renderAssignments() {
    const list = document.getElementById("assignment-list");
    const totalCount = document.getElementById("total-count");
    const completedCount = document.getElementById("completed-count");
    const remainingCount = document.getElementById("remaining-count");

    if (!list || !totalCount || !completedCount || !remainingCount) {
        console.error("Даалгаврын HTML элементүүд олдсонгүй.");
        return;
    }

    const completed = assignments.filter(
        item => item.completed
    ).length;

    totalCount.textContent = assignments.length;
    completedCount.textContent = completed;
    remainingCount.textContent = assignments.length - completed;
const searchInput = document.getElementById("assignment-search");
const statusFilter = document.getElementById("assignment-status");

const searchText = searchInput
    ? searchInput.value.trim().toLowerCase()
    : "";

const selectedStatus = statusFilter
    ? statusFilter.value
    : "all";

const filteredAssignments = assignments.filter(item => {
    const matchesSearch =
        item.title.toLowerCase().includes(searchText) ||
        item.course.toLowerCase().includes(searchText);

    const matchesStatus =
        selectedStatus === "all" ||
        (selectedStatus === "completed" && item.completed) ||
        (selectedStatus === "incomplete" && !item.completed);

    return matchesSearch && matchesStatus;
});
    list.replaceChildren();

if (assignments.length === 0) {
    const message = document.createElement("p");
    message.textContent = "Одоогоор даалгавар алга.";
    list.appendChild(message);
    return;
}

if (filteredAssignments.length === 0) {
    const message = document.createElement("p");
    message.textContent = "Тохирох даалгавар олдсонгүй.";
    list.appendChild(message);
    return;
}

filteredAssignments.forEach(item => {
        const article = document.createElement("article");
        article.className = "assignment-item";
        // Даалгаврын хугацааг шалгах
if (!item.completed) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const deadlineDate = new Date(item.deadline + "T00:00:00");
    const diffTime = deadlineDate.getTime() - today.getTime();
    const daysLeft = Math.round(diffTime / (1000 * 60 * 60 * 24));

    if (daysLeft < 0) {
        article.classList.add("overdue");
    } else if (daysLeft <= 3) {
        article.classList.add("due-soon");
    } else {
        article.classList.add("upcoming");
    }
}

        if (item.completed) {
            article.classList.add("completed");
        }

        const info = document.createElement("div");

        const title = document.createElement("h3");
        title.textContent = item.title;

        const course = document.createElement("p");
        course.textContent = `Хичээл: ${item.course}`;

        const deadline = document.createElement("p");
        deadline.textContent = `Дуусах хугацаа: ${item.deadline}`;

        info.append(title, course, deadline);

        const actions = document.createElement("div");
        actions.className = "assignment-actions";

        const completeButton = document.createElement("button");
        completeButton.type = "button";
        completeButton.textContent = item.completed
            ? "Буцаах"
            : "Дууссан";

        completeButton.addEventListener("click", () => {
            toggleAssignment(item.id);
        });

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "delete-button";
        deleteButton.textContent = "Устгах";

        deleteButton.addEventListener("click", () => {
            deleteAssignment(item.id);
        });

        actions.append(completeButton, deleteButton);
        article.append(info, actions);
        list.appendChild(article);
    });
}

const form = document.getElementById("assignment-form");

form.addEventListener("submit", async event => {
    event.preventDefault();

    const title = document
        .getElementById("assignment-title")
        .value.trim();

    const course = document
        .getElementById("assignment-course")
        .value.trim();

    const deadline = document
        .getElementById("assignment-deadline")
        .value;

    if (!title || !course || !deadline) {
        alert("Бүх талбарыг бөглөнө үү.");
        return;
    }

    await addAssignment(title, course, deadline);

    form.reset();
});
const searchInput = document.getElementById("assignment-search");
const statusFilter = document.getElementById("assignment-status");

if (searchInput) {
    searchInput.addEventListener("input", renderAssignments);
}

if (statusFilter) {
    statusFilter.addEventListener("change", renderAssignments);
}
// ========================================
// AI Campus Assistant - Chat
// ========================================

const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const chatMessages = document.getElementById("chat-messages");

// Чатанд шинэ мессеж нэмэх
function addChatMessage(message, sender) {
    const messageElement = document.createElement("div");

    messageElement.classList.add("chat-message");

    if (sender === "user") {
        messageElement.classList.add("user-message");
    } else {
        messageElement.classList.add("bot-message");
    }

    // Хэрэглэгчийн оруулсан текстийг HTML гэж ажиллуулахгүй
    messageElement.textContent = message;

    chatMessages.appendChild(messageElement);

    // Хамгийн сүүлийн мессеж рүү гүйлгэх
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Хариултын текстийг бэлтгэх
function generateAssistantResponse(question) {
    const text = question.toLowerCase().trim();

    // API-аас одоогийн даалгавруудыг авах
    return fetch(API_URL)
        .then(response => {
            if (!response.ok) {
                throw new Error("Даалгавруудыг уншиж чадсангүй.");
            }

            return response.json();
        })
        .then(tasks => {
            const incompleteTasks = tasks.filter(task => !task.completed);
            const completedTasks = tasks.filter(task => task.completed);

            // Нийт даалгаврын тоо
            if (
                text.includes("хэдэн") &&
                (text.includes("даалгавар") || text.includes("task"))
            ) {
                return `Нийт ${tasks.length} даалгавар байна. Дууссан: ${completedTasks.length}, үлдсэн: ${incompleteTasks.length}.`;
            }

            // Дууссан даалгаврууд
            if (
                text.includes("дууссан") ||
                text.includes("completed")
            ) {
                if (completedTasks.length === 0) {
                    return "Одоогоор дууссан даалгавар алга байна.";
                }

                return "Дууссан даалгаврууд: " +
                    completedTasks.map(task => task.title).join(", ");
            }

            // Дуусаагүй даалгаврууд
            if (
                text.includes("үлдсэн") ||
                text.includes("дуусаагүй") ||
                text.includes("incomplete")
            ) {
                if (incompleteTasks.length === 0) {
                    return "Бүх даалгавар дууссан байна. Баяр хүргэе! 🎉";
                }

                return "Дуусаагүй даалгаврууд: " +
                    incompleteTasks.map(task => task.title).join(", ");
            }

            // Хамгийн ойрын хугацаатай даалгавар
            if (
                text.includes("ойрын") ||
                text.includes("хугацаа") ||
                text.includes("deadline")
            ) {
                const tasksWithDeadline = incompleteTasks
                    .filter(task => task.deadline)
                    .sort((a, b) => a.deadline.localeCompare(b.deadline));

                if (tasksWithDeadline.length === 0) {
                    return "Хугацаатай дуусаагүй даалгавар олдсонгүй.";
                }

                const task = tasksWithDeadline[0];

                return `Хамгийн ойрын хугацаатай даалгавар: ${task.title}. Дуусах хугацаа: ${task.deadline}.`;
            }

            // Тусламж
            if (
                text.includes("тусламж") ||
                text.includes("help")
            ) {
                return "Та дараах асуултуудыг асууж болно: 'Ямар даалгавар үлдсэн бэ?', 'Хэдэн даалгавар үлдсэн бэ?', 'Дууссан даалгаврууд юу вэ?', 'Хамгийн ойрын хугацаатай даалгавар юу вэ?'";
            }

            return "Таны асуултыг бүрэн ойлгосонгүй. 'Ямар даалгавар үлдсэн бэ?' эсвэл 'Хамгийн ойрын хугацаатай даалгавар юу вэ?' гэж асуугаад үзээрэй.";
        });
}

// Хэрэглэгчийн асуултыг илгээх
if (chatForm) {
    chatForm.addEventListener("submit", async function (event) {
        event.preventDefault();

        const question = chatInput.value.trim();

        if (!question) {
            return;
        }

        addChatMessage(question, "user");

        chatInput.value = "";
        chatInput.focus();

        try {
            const answer = await generateAssistantResponse(question);
            addChatMessage(answer, "bot");
        } catch (error) {
            console.error("Chat error:", error);

            addChatMessage(
                "Уучлаарай, даалгаврын мэдээллийг авч чадсангүй. Backend сервер ажиллаж байгаа эсэхийг шалгана уу.",
                "bot"
            );
        }
    });
}
loadAssignments();

console.log("AI Campus Assistant: API холболт эхэллээ.");
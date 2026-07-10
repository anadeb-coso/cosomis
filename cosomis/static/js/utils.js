function moneyFormat(money, unit = "FCFA") {
    let list_money_str = String(Math.floor(money)).split("").reverse();
    let money_format = "";
    for (let i = 1; i <= list_money_str.length; i++) {
        money_format += list_money_str[i - 1];
        if (i % 3 == 0) {
            money_format += " "
        }
    }
    return money_format.split("").reverse().join("") + " " + unit;
}


// Fonction pour récupérer le token CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function pushNotify(
    message, 
    type = "error",
    timeout = 10000 // Durée avant disparition en ms
) {
    const notif = document.createElement("div");

    notif.style.background = type === "error" ? "#e74c3c" : "#2ecc71";
    notif.style.color = "#fff";
    notif.style.padding = "12px 18px";
    notif.style.marginTop = "10px";
    notif.style.borderRadius = "8px";
    notif.style.boxShadow = "0 2px 10px rgba(0,0,0,0.3)";
    notif.style.fontSize = "15px";
    notif.style.fontFamily = "Arial";
    notif.style.transform = "translateX(120%)";
    notif.style.transition = "transform 0.5s ease";

    notif.innerText = message;

    document.getElementById("push-notification-container").appendChild(notif);

    // Animation entrée
    setTimeout(() => {
        notif.style.transform = "translateX(0)";
    }, 50);

    // Disparition après 4 secondes
    setTimeout(() => {
        notif.style.transform = "translateX(120%)";
        setTimeout(() => notif.remove(), 500);
    }, timeout);
}

function getInitials(str) {
    if (!str || str.trim() === '') {
        return 'N';
    }

    return str
        .trim()
        .split(' ')
        .filter(word => word.length > 0)
        .map(word => word[0])
        .join('')
        .toUpperCase();
}

function stringToDateUTC(dateTime) {
    if (!dateTime) return null;

    const date = new Date(dateTime);

    return {
        year: date.getUTCFullYear(),
        month: date.getUTCMonth() + 1,
        day: date.getUTCDate(),
        hours: date.getUTCHours(),
        minutes: date.getUTCMinutes(),
        seconds: date.getUTCSeconds()
    };
}
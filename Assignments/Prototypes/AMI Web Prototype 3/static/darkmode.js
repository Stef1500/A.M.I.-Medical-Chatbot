document.addEventListener("DOMContentLoaded", () => {

    let darkmode = localStorage.getItem('darkmode');
    const changeMode = document.getElementById('change-mode');

    const enableDarkMode = () => {
        document.body.classList.add('darkmode');
        localStorage.setItem('darkmode', 'active');
    }

    const disableDarkMode = () => {
        document.body.classList.remove('darkmode');
        localStorage.setItem('darkmode', 'inactive'); // ✅ fixed
    }

    if (darkmode === "active") {
        enableDarkMode();
        if (changeMode) changeMode.checked = true;
    } else {
        disableDarkMode();
        if (changeMode) changeMode.checked = false;
    }

    if (changeMode) {
        changeMode.addEventListener("change", () => {
            if (changeMode.checked) {
                enableDarkMode();
            } else {
                disableDarkMode();
            }
        });
    }
});

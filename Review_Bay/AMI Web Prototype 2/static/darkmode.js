/*NF: Created "Darkmode" Javascript file*/
/*Reference Material: https://www.youtube.com/watch?v=_gKEUYarehE*/
let darkmode = localStorage.getItem('darkmode')
const changeMode = document.getElementById('change-mode')

const enableDarkMode = () => {
    document.body.classList.add('darkmode')
    localStorage.setItem('darkmode', 'active')
}

const disableDarkMode = () => {
    document.body.classList.remove('darkmode')
    localStorage.setItem('darkmode', null)
}

if(darkmode === "active") enableDarkMode()

changeMode.addEventListener("click", () => {
    darkmode = localStorage.getItem('darkmode')
    darkmode !== "active" ? enableDarkMode() : disableDarkMode()
})
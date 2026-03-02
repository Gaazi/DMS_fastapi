document.addEventListener("DOMContentLoaded", () => {
    // Mobile navbar toggle
    const navbarToggle = document.getElementById("navbar-toggle");
    const navbarMenu = document.getElementById("navbar-menu");

    if (navbarToggle && navbarMenu) {
        navbarToggle.addEventListener("click", () => {
            navbarMenu.classList.toggle("hidden");
        });
    }
   
   
   
   // General dropdown handling (for other menus)
    const setupDropdown = (triggerId, menuId) => {
        const trigger = document.getElementById(triggerId);
        const menu = document.getElementById(menuId);

        if (trigger && menu) {
            trigger.addEventListener("click", (e) => {
                e.stopPropagation();  // Prevent event from bubbling up
                menu.classList.toggle("hidden");
            });

            // Close the dropdown if clicked outside
            document.addEventListener("click", (e) => {
                if (!menu.contains(e.target) && !trigger.contains(e.target)) {
                    menu.classList.add("hidden");
                }
            });
        }
    };

    // Initialize dropdowns
    setupDropdown("tools-dropdown", "tools-menu");
    setupDropdown("category-dropdown", "category-menu");
   
   
   
//  Close DOM Content Loaded  Function
});



// Google Drive Direct Download Copy Link
function copyLink() {
    var copyText = document.getElementById("generatedLink");
    copyText.select();
    copyText.setSelectionRange(0, 99999); /* For mobile devices */
    document.execCommand("copy");

    var copyButton = document.querySelector(".copy-button");
    copyButton.textContent = "Copied ✔";
    copyButton.classList.add("copied");

    setTimeout(function() {
        copyButton.textContent = "Copy Link";
        copyButton.classList.remove("copied");
    }, 5000);
}

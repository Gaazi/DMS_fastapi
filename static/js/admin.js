document.addEventListener("DOMContentLoaded", function () {
    const radioInputs = document.querySelectorAll("input[name='upload_option']");
    const newUploadSection = document.querySelector(".new-upload");
    const bunnyUploadSection = document.querySelector(".bunny-upload");

    function toggleUploadSections() {
        const selected = document.querySelector("input[name='upload_option']:checked").value;
        if (selected === "new") {
            newUploadSection.style.display = "block";
            bunnyUploadSection.style.display = "none";
        } else {
            newUploadSection.style.display = "none";
            bunnyUploadSection.style.display = "block";
        }
    }

    radioInputs.forEach(input => {
        input.addEventListener("change", toggleUploadSections);
    });

    toggleUploadSections();  // Initial call
});

document.addEventListener("DOMContentLoaded", () => {
  const input = document.querySelector(".profile-photo-input");
  const preview = document.getElementById("profilePhotoPreview");
  const fallback = document.getElementById("profilePhotoFallback");

  if (!input || !preview) return;

  input.addEventListener("change", () => {
    const file = input.files && input.files[0];
    if (!file || !file.type.startsWith("image/")) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      preview.src = event.target.result;
      preview.hidden = false;
      if (fallback) fallback.style.display = "none";
    };
    reader.readAsDataURL(file);
  });
});

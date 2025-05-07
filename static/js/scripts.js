document.addEventListener('click', function(event) {
    const drawer = document.querySelector('.drawer');
    const toggleBtn = document.querySelector('.toggle-btn');

    // تحقق إذا لم يكن النقر داخل الـ drawer أو على زر الفتح
    if (!drawer.contains(event.target) && !toggleBtn.contains(event.target)) {
        drawer.classList.remove('open');
    }
});
document.querySelector('.toggle-btn').addEventListener('click', function(event) {
    document.querySelector('.drawer').classList.toggle('open');
    event.stopPropagation(); // يمنع انتشار الحدث
});

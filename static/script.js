document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("portForm");
    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const portId = document.getElementById("port").value;
        const notificationMethod = document.getElementById("notification-method").value;

        try {
            const response = await fetch('/set_port', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ port_id: portId, notification_method: notificationMethod })
            });

            if (response.ok) {
                alert("登録が成功しました！");
                window.location.reload(); // ページを更新してリストをリロード
            } else {
                alert("登録に失敗しました！");
            }
        } catch (error) {
            console.error("エラー:", error);
            alert("エラーが発生しました。");
        }
    });
});

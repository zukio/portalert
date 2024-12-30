document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("portForm");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const portId = document.getElementById("port").value;
  });
});

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("portForm");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const portId = document.getElementById("port").value;
    const webhookUrl = document.getElementById("webhook_url").value;

    try {
      const response = await fetch("/set_port", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ port_id: portId, webhook_url: webhookUrl }),
      });

      if (response.ok) {
        alert("登録が成功しました！");
        window.location.reload(); // ページを更新
      } else {
        alert("登録に失敗しました！");
      }
    } catch (error) {
      console.error("エラー:", error);
      alert("エラーが発生しました。");
    }
  });
});

// Seeds a demo room over the public API. One HTTP client per person, so each
// gets its own session cookie, exactly like three separate devices.
const BASE = process.env.BASE || "http://127.0.0.1:7284";
const PW = process.env.PW || "frontroom";
const fs = require("fs");

function client() {
  let cookie = "";
  async function call(path, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (cookie) headers.cookie = cookie;
    if (options.json !== undefined) {
      headers["content-type"] = "application/json";
      options.body = JSON.stringify(options.json);
    }
    const response = await fetch(BASE + path, { method: options.method || "GET", headers, body: options.body });
    const set = response.headers.getSetCookie ? response.headers.getSetCookie() : [];
    if (set.length) cookie = set.map((entry) => entry.split(";")[0]).join("; ");
    const text = await response.text();
    let data = null;
    try {
      data = JSON.parse(text);
    } catch (error) {
      data = { raw: text.slice(0, 200) };
    }
    if (!response.ok) throw new Error(`${path} ${response.status} ${JSON.stringify(data).slice(0, 200)}`);
    return data;
  }
  return { call };
}

async function join(name) {
  const c = client();
  await c.call("/api/session", {
    method: "POST",
    json: { name, password: PW, device_key: `seed-${name.toLowerCase()}` },
  });
  return c;
}

async function say(c, roomId, body, extra = {}) {
  return c.call("/api/messages", {
    method: "POST",
    json: { room_id: roomId, body, ...extra },
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const mara = await join("Mara");
  const jonas = await join("Jonas");
  const ada = await join("Ada");
  await sleep(300);

  const first = await say(mara, "main", "Coffee is ready. Mugs are on the shelf above the kettle.");
  await sleep(200);
  await say(
    mara,
    "main",
    "The fibre installer comes Thursday between 9 and 11. I will be out, so someone needs to let him in."
  );
  await sleep(200);
  const reply = await say(mara, "main", "Leaving the side gate open from eight.");
  await sleep(200);
  await jonas.call(`/api/messages/${reply.message.id}/reactions`, {
    method: "POST",
    json: { emoji: "👍" },
  });
  await sleep(200);
  await say(jonas, "main", "I will take the morning slot. Working from the front room anyway.");

  // Ada uploads the label image, then posts it into the room.
  const form = new FormData();
  const file = new Blob([fs.readFileSync("/home/user/HostTalk/static/screenshots/demo-label.png")], {
    type: "image/png",
  });
  form.append("file", file, "front-room-label.png");
  const uploadResponse = await fetch(BASE + "/api/uploads", {
    method: "POST",
    body: form,
    headers: { cookie: await cookieFor("Ada") },
  });
  const uploaded = await uploadResponse.json();
  if (!uploadResponse.ok) throw new Error("upload failed " + JSON.stringify(uploaded).slice(0, 200));
  const attachmentId = uploaded.attachment.id;
  await ada.call("/api/messages", {
    method: "POST",
    json: {
      room_id: "main",
      body: "Label draft, second pass.",
      kind: "image",
      attachment_id: attachmentId,
    },
  });
  await sleep(300);
  const quoted = await mara.call("/api/messages", {
    method: "POST",
    json: {
      room_id: "main",
      body: "Second pass, please. Keep the band and calm the body text.",
      quote_id: first.message.id,
    },
  });
  console.log("quote", quoted.message ? "ok" : JSON.stringify(quoted).slice(0, 160));

  // A group room with the three people plus a locked direct thread.
  const room = await mara.call("/api/rooms", {
    method: "POST",
    json: { name: "Kitchen plans" },
  });
  const roomId = room.room.id;
  const invite = await mara.call(`/api/rooms/${roomId}/invite`, { method: "POST" });
  for (const [c, name] of [[jonas, "Jonas"], [ada, "Ada"]]) {
    try {
      await c.call("/api/rooms/join", { method: "POST", json: { code: invite.code } });
      console.log("joined", name);
    } catch (error) {
      console.log("join failed", name, error.message);
    }
  }
  await say(mara, roomId, "Room for the kitchen work. Plans, dates, receipts.");
  await say(ada, roomId, "Paint swatches land tomorrow. Two warm options, one grey.");

  const people = await mara.call("/api/people");
  const jonasId = people.people.find((person) => person.name === "Jonas").id;
  const dm = await mara.call("/api/dm", { method: "POST", json: { user_id: jonasId } });
  await say(mara, dm.room.id, "Saturday works for the router swap. I will bring the ladder.");
  await say(jonas, dm.room.id, "Good. I will move the shelf first.");
  console.log("dm", dm.room.id);
  console.log("done");
})();

async function cookieFor(name) {
  const c = client();
  const response = await fetch(BASE + "/api/session", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, password: PW, device_key: `seed-${name.toLowerCase()}` }),
  });
  const set = response.headers.getSetCookie();
  return set.map((entry) => entry.split(";")[0]).join("; ");
}

// Seeds a demo room over the public API. One HTTP client per person, so each
// gets its own session cookie, exactly like three separate devices.
//
// Run against a fresh data folder:
//   node docs/seed-demo.js
//
// The screenshots in static/screenshots come from this room. Every name and
// message is a placeholder.
const BASE = process.env.BASE || "http://127.0.0.1:7284";
const PW = process.env.PW || "frontroom";
const ASSETS = process.env.ASSETS || "/tmp/cap/assets";
const fs = require("fs");
const path = require("path");

function client(deviceKey) {
  let cookie = "";
  async function call(route, options = {}) {
    const headers = { ...(options.headers || {}) };
    if (cookie) headers.cookie = cookie;
    if (options.json !== undefined) {
      headers["content-type"] = "application/json";
      options.body = JSON.stringify(options.json);
    }
    const response = await fetch(BASE + route, {
      method: options.method || "GET",
      headers,
      body: options.body,
    });
    const set = response.headers.getSetCookie ? response.headers.getSetCookie() : [];
    if (set.length) cookie = set.map((entry) => entry.split(";")[0]).join("; ");
    const text = await response.text();
    let data = null;
    try {
      data = JSON.parse(text);
    } catch (error) {
      data = { raw: text.slice(0, 200) };
    }
    if (!response.ok) {
      throw new Error(`${route} ${response.status} ${JSON.stringify(data).slice(0, 240)}`);
    }
    return data;
  }
  async function upload(route, field, filePath, filename, extra = {}) {
    const form = new FormData();
    const type = filename.endsWith(".png") ? "image/png" : "application/octet-stream";
    for (const [key, value] of Object.entries(extra)) form.append(key, value);
    form.append(field, new Blob([fs.readFileSync(filePath)], { type }), filename);
    const response = await fetch(BASE + route, { method: "POST", body: form, headers: { cookie } });
    const data = await response.json();
    if (!response.ok) throw new Error(`${route} ${response.status} ${JSON.stringify(data).slice(0, 240)}`);
    return data;
  }
  return { call, upload };
}

async function join(name, key) {
  const c = client(key);
  await c.call("/api/session", {
    method: "POST",
    json: { name, password: PW, device_key: key },
  });
  return c;
}

async function say(c, roomId, body, extra = {}) {
  return c.call("/api/messages", { method: "POST", json: { room_id: roomId, body, ...extra } });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const mara = await join("Mara", "seed-mara");
  const jonas = await join("Jonas", "seed-jonas");
  const ada = await join("Ada", "seed-ada");
  await sleep(400);

  // Pictures for two of the three. Ada keeps her initials, which shows the fallback.
  for (const [who, file] of [
    [mara, "mara.png"],
    [jonas, "jonas.png"],
  ]) {
    await who.upload("/api/me/avatar", "avatar", path.join(ASSETS, file), file);
  }

  // Badges: one icon plus up to four characters.
  await mara.call("/api/me", { method: "PATCH", json: { badge_icon: "room", badge_text: "HOME" } });
  await jonas.call("/api/me", { method: "PATCH", json: { badge_icon: "hash", badge_text: "JON" } });

  // A custom emoji, added by the host.
  const emojiData = await mara.upload(
    "/api/emoji",
    "file",
    path.join(ASSETS, "mug.png"),
    "mug.png",
    { name: "mug" }
  );
  console.log("emoji", emojiData.emoji.token);

  // The main thread, in the order the shots read: the image sits above the
  // fold so the text below it fits in one view.
  await say(mara, "main", "Coffee is ready. Mugs are on the shelf above the kettle.");
  await sleep(200);

  const uploaded = await ada.upload(
    "/api/uploads",
    "file",
    "/home/user/HostTalk/static/screenshots/demo-label.png",
    "front-room-label.png"
  );
  const labelled = await ada.call("/api/messages", {
    method: "POST",
    json: {
      room_id: "main",
      body: "Label draft, second pass.",
      kind: "image",
      attachment_id: uploaded.attachment.id,
    },
  });
  await sleep(250);

  const pinned = await say(
    mara,
    "main",
    "The fibre installer comes Thursday between 9 and 11. I will be out, so someone needs to let him in."
  );
  await sleep(200);

  const reacted = await say(mara, "main", "Leaving the side gate open from eight.");
  await sleep(200);
  for (const [who, emoji] of [
    [jonas, "👍"],
    [ada, "🙂"],
    [ada, emojiData.emoji.token],
  ]) {
    await who.call(`/api/messages/${reacted.message.id}/reactions`, { method: "POST", json: { emoji } });
    await sleep(120);
  }

  await say(jonas, "main", "I will take the morning slot. Working from the front room anyway.");
  await sleep(200);

  // A quote, then an edit, so the thread shows both.
  const quoted = await mara.call("/api/messages", {
    method: "POST",
    json: {
      room_id: "main",
      body: "Second pass, please. Keep the band and calm the body text.",
      quote_id: labelled.message.id,
    },
  });
  await sleep(150);
  await mara.call(`/api/messages/${quoted.message.id}`, {
    method: "PATCH",
    json: { body: "Second pass, please. Keep the band and calm the body text." },
  });

  // A pin, so the pinned sheet has something in it. Mara is the host.
  await mara.call(`/api/messages/${pinned.message.id}/pin`, { method: "POST", json: { pinned: true } });

  // A group room inside the main room, and a room inside that one, locked.
  const kitchen = await mara.call("/api/rooms", { method: "POST", json: { name: "Kitchen plans" } });
  const kitchenId = kitchen.room.id;
  const invite = await mara.call(`/api/rooms/${kitchenId}/invite`, { method: "POST" });
  for (const [c, name] of [
    [jonas, "Jonas"],
    [ada, "Ada"],
  ]) {
    try {
      await c.call("/api/rooms/join", { method: "POST", json: { code: invite.code } });
      console.log("joined", name);
    } catch (error) {
      console.log("join failed", name, error.message);
    }
  }
  await say(mara, kitchenId, "Room for the kitchen work. Plans, dates, receipts.");
  await sleep(150);
  await say(ada, kitchenId, "Paint swatches land tomorrow. Two warm options, one grey.");
  await sleep(150);
  await say(jonas, kitchenId, "The tap arrives Friday. I will fit it Saturday morning.");

  const roof = await mara.call("/api/rooms", {
    method: "POST",
    json: { name: "Roof work", parent_id: kitchenId, password: "ladder" },
  });
  console.log("roof", roof.room.id);
  await say(mara, roof.room.id, "Scaffold quote is in. Two days, weather permitting.");

  // A direct thread with a password on it, which shows the lock in the rail.
  const people = await mara.call("/api/people");
  const jonasId = people.people.find((person) => person.name === "Jonas").id;
  const dm = await mara.call("/api/dm", { method: "POST", json: { user_id: jonasId } });
  await mara.call(`/api/rooms/${dm.room.id}/password`, { method: "POST", json: { password: "router" } });
  await say(mara, dm.room.id, "Saturday works for the router swap. I will bring the ladder.");
  await jonas.call("/api/rooms/" + dm.room.id + "/verify", { method: "POST", json: { password: "router" } });
  await say(jonas, dm.room.id, "Good. I will move the shelf first.");
  console.log("dm", dm.room.id);

  console.log("done");
})();

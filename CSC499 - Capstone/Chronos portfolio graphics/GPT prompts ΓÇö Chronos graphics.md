# ChatGPT prompts — Chronos portfolio graphics

Paste these into the same chat you used for the poster, so it still has the mascot
and the style in context. The style block below is there in case the thread has
drifted — it restates what your poster actually uses, sampled from the PDF.

---

## Style block — paste once at the top of any new request

> Keep the exact visual system from the Chronos poster:
> background a soft light-blue gradient (#F7FBFE at the top to #D7EBFB at the
> bottom) with faint wavy bands and small four-point sparkles; white rounded cards
> with very soft blue shadows and ~18px corner radius; section headers as rounded
> pill banners in a blue gradient (#0B4FBE to #2E8BF0) with white bold uppercase
> text; headings in deep navy #032654; accent text in #2490FC; supporting text in
> #5E7A9B. Tint colours for grouped boxes: blue #CCE6FD, green #D2F7E5, purple
> #E5E5FD, peach #FEE8CE. Typeface is Poppins — Bold for headings, Medium and
> Regular for body. Flat vector style, no photographic texture, no drop shadows on
> type, generous white space.

---

## 1 · Mascot — regenerate at high resolution

The clock character in your poster only exists at about 250 px, because Canva
flattened the PDF. Regenerate it properly before using it anywhere large.

> Full-body mascot character on a fully transparent background, flat vector
> illustration with a clean dark navy outline. A friendly round alarm clock with
> two bells on top, a cream clock face with simple black hands, large expressive
> cartoon eyes, a cheerful open smile, light blue body (#4FA3E8), white gloved
> hands and chunky white boots with navy accents. Confident, energetic pose.
> Thick consistent linework, soft cel shading only, no gradients, no background,
> no shadow on the floor. Square canvas, at least 2048 × 2048, PNG with alpha.

**Pose variants** — same prompt, swap the pose sentence:

| Use | Pose sentence |
|---|---|
| Hero | "standing confidently, one arm raised and pointing forward to the right" |
| Features | "holding up a clipboard with a checklist, giving a thumbs up" |
| Architecture | "sitting cross-legged working on a laptop, focused expression" |
| Team | "waving with both arms, big friendly smile" |
| Video outro | "giving a two-handed thumbs up, confetti sparkles around" |

---

## 2 · Hero / title graphic — 1920 × 1080

> Create a 1920 × 1080 landscape title graphic for a university capstone project
> called **Chronos — An Automated Timetabling Solution**. Layout: left half holds a
> small letter-spaced eyebrow "AUTOMATED TIMETABLING" in medium blue, then the word
> "Chronos" very large in Poppins Bold deep navy with a thin white outline, then
> the line "Conflict-free schedules, solved by CP-SAT" in bold blue, then a wide
> blue gradient pill containing "Smarter schedules. Better learning." in white
> bold, then three small white pill chips reading "1 MODEL", "2 SOLVE", "3 REPAIR".
> The clock mascot stands at the bottom left. The right half is a large white
> rounded card showing a weekly university timetable grid, Monday to Friday across
> the top and hours 08 to 15 down the side, with about ten coloured class blocks in
> blue, navy, teal, purple and amber, each labelled with a course code. A small
> green pill in the card's top right reads "OPTIMAL · 0 clashes". Institutional
> logos sit in the top right corner. [style block]

---

## 3 · Main features — 800 × 600

> Create an 800 × 600 graphic titled "MAIN FEATURES" in a blue gradient pill at the
> top centre, with the subtitle "Smarter schedules. Better learning." beneath it.
> Below, five equal white rounded cards in a single row, each with a pale blue
> circle holding a simple flat blue icon, a small numbered navy badge in the circle's
> top right, a two-line bold navy title and one line of grey supporting text. The
> five are: 1 Instructor availability — must, preferred or any time; 2 Room &
> capacity — seats and computer limits; 3 Preference scoring — soft rules ranked,
> not forced; 4 Schedule repair mode — adapts when an input changes; 5 Interactive
> calendar — visual, versioned, friendly. Small faint arrows between the cards.
> Underneath, a centred label "ALSO IN CHRONOS" and four white pill chips: Student
> groups, Conflict handling, Versioning, Multi-agent ready. [style block]

---

## 4 · System architecture — 800 × 600

> Create an 800 × 600 architecture diagram titled "SYSTEM ARCHITECTURE" in a blue
> gradient pill at the top centre, subtitle "From raw course data to a published
> timetable". Three zones connected by arrows. Left: a pale blue rounded box headed
> "USER INPUT" listing Course data, Instructor availability, Room information,
> Preferences & constraints. Centre, larger: a pale green rounded box headed
> "CP-SAT OPTIMISATION" containing a white pill "Google OR-Tools", a green pill
> "Python · CP-SAT solver", and a two-by-two grid of small white cards reading
> Conflict check / hard constraints, Score & ranking / soft weights, Repair mode /
> adapt to change, Versioning / track iterations. Right, stacked: a peach box
> "WEB APPLICATION — React · Vue · Tailwind, interactive calendar view" and a purple
> box "DATABASE — PostgreSQL, schedules & versions". Below the centre, a
> dashed-outline box "MAS · FUTURE WORK — AI agents + NLP for negotiated
> rescheduling". A faint footer line reads "Deployed with Docker · Vercel · GitHub ·
> n8n automations". [style block]

---

## 5 · Team — 800 × 600

> Create an 800 × 600 team graphic. At the top, a letter-spaced eyebrow
> "SMARTER · SCHEDULES" in medium blue, then the headline "The Team Behind Chronos"
> with "The Team Behind" in deep navy and "Chronos" in bright blue. Below, three
> white rounded photo cards in a row. Each card holds a portrait photograph with
> rounded corners filling the upper two thirds, a small coloured role pill
> overlapping the photo's lower edge, then the person's name in bold navy and,
> for the student, a student ID in bright blue. A row of thin grey vertical dashes
> sits at the bottom of each card like a barcode. The three roles are PROJECT
> MEMBER in blue, ADVISOR in green and CO-ADVISOR in purple. Footer line: "KMUTT ·
> School of Information Technology · CSC499 Capstone Project 2026". [style block]

---

## Why the versions I built may still be easier

Image models cannot place a photograph you supply, and they garble small text — the
course codes in the timetable grid and the student ID will come back as nonsense
letters. The PNGs in this folder have real text and your real photos. Use these
prompts if you want a different look, or to regenerate the mascot at a size that
actually holds up.

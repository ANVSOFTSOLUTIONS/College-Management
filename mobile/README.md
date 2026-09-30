# ANV College — mobile app

One React Native (Expo) app for **students, parents, faculty and HODs** — these users work only in the app. The sign-in
screen has three tabs; after sign-in the app shows the screens for that role.
It uses the same backend API as the website. College admins and office staff use
the website.

| Role | Signs in with | Screens |
|---|---|---|
| Student | College code + roll number | Home (attendance %, fees due, hostel, bus, library books, remarks), Results (grades, SGPA, CGPA), Assignments, Notices, Timetable, Leave, Placements (apply to drives) |
| Parent | Mobile number | Same as a student, for each child (switch at the top), without Placements |
| Faculty | College email | Punch in / out, Attendance (tap to mark present / absent / late), Marks entry, Assignments (post / delete), approve / reject their students' leave, student remarks, Payslips, Timetable, Notices, own Leave |
| HOD | College email (a faculty member set as head of department) | Everything faculty have, plus a **Dept** tab: faculty punch status today, each batch's attendance today, students below 75% attendance, and approving department faculty's leave |

First sign-in asks for a new password. Tabs for modules the college has
switched off (exams, assignments, notices, timetable, placements) are hidden.

## Run on your phone (development)

1. Start the backend so the phone can reach it (same Wi-Fi):
   ```
   cd backend
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. Point the app at your PC's IP address (`ipconfig` shows it):
   ```
   cd mobile
   copy .env.example .env        # then edit EXPO_PUBLIC_API_URL=http://<your-PC-IP>:8000/api/v1
   npm install
   npx expo start
   ```
3. Install **Expo Go** from the Play Store and scan the QR code.

With the sample college (`python -m scripts.college_seed`): student `ANVCOL` /
`24A91A0501` / `Student@123`, parent `9848000101` / `Parent@123`, faculty
`faculty1@anvcollege.in` / `Faculty@12345`.

`EXPO_PUBLIC_WEB_URL` (optional) is the college website; when set, the fee card
shows "Pay online", which opens the website's payment page.

## Build for the Play Store

Builds run in the cloud with EAS (no Android Studio needed):

```
npx eas-cli@latest login
npx eas-cli@latest build --platform android --profile preview      # an .apk to share for testing
npx eas-cli@latest build --platform android --profile production   # an .aab for the Play Store
```

Set `EXPO_PUBLIC_API_URL` to the live **https** API before a production build
(Android blocks plain http in release builds). The package id is
`com.anvsoftsolutions.college` (in `app.json`).

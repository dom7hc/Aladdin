---
marp: true
paginate: true
theme: default
---

<!--
CÁCH RENDER THÀNH SLIDE / POWERPOINT
- VS Code: cài extension "Marp for VS Code" → mở file → Export (PDF / PPTX / HTML)
- CLI:    npx @marp-team/marp-cli docs/aladdin-pitch-deck.md --pptx
- Mỗi dấu "---" là ranh giới một slide.
-->

# **Aladdin**
## AI PoC Builder

**Biến một ý tưởng mơ hồ thành PoC có cấu trúc, đã review và sẵn sàng bàn giao cho DevOps.**

`Idea → Requirements → Architecture → Code → Review → Test → Handoff`

<!-- _footer: Hackathon project · Aladdin · AI PoC Builder -->

---

## 1. Vấn đề

- **Ý tưởng thì nhanh, PoC thì chậm.** Muốn kiểm chứng một ý tưởng phải qua BA → kiến trúc → code → test → bàn giao. Mỗi bước là một tuần.
- **"Prompt → code" chưa đủ.** AI sinh code trực tiếp từ một câu prompt thường *không khớp yêu cầu*, thiếu cấu trúc, khó kiểm soát chất lượng.
- **Không có nguồn sự thật.** Chat history rời rạc, không ai biết yêu cầu đã đủ chưa, còn thiếu gì.
- **Không có vòng kiểm soát.** Không review, không chạy build/test, DevOps nhận một mớ code không rõ trạng thái.

> Khoảng cách giữa **"ý tưởng"** và **"thứ gì đó chạy được để demo"** chính là chỗ tốn thời gian nhất.

---

## 2. Giải pháp: Aladdin

Aladdin là một **nền tảng multi-agent workflow** dẫn dắt người dùng — kể cả người không rành kỹ thuật — đi trọn hành trình:

```text
Ý tưởng
  ↓
Chatbot gom yêu cầu có cấu trúc
  ↓
Requirements (JSON + MD)
  ↓
Architect Agent → Architecture
  ↓
Developer Agent → Source code
  ↓
Reviewer Agent → Review
  ↓
Tester Agent → Build / Test
  ↓
PoC sẵn sàng bàn giao cho DevOps
```

**Mục tiêu không phải phần mềm production**, mà chứng minh rằng một ý tưởng mơ hồ có thể trở thành **PoC có cấu trúc, đã review, build được**.

---

## 3. Giá trị cốt lõi

> **Aladdin biến một ý tưởng kinh doanh thành PoC phần mềm có cấu trúc, đã review và build được thông qua một quy trình AI có hướng dẫn.**

Ngắn gọn:

```text
Idea → Understand → Design → Build → Review → Test → Deploy
```

**Thay vì** để AI generate mù quáng từ prompt, nền tảng:
1. **Hiểu** yêu cầu trước,
2. **Thiết kế** kiến trúc,
3. **Sinh code**,
4. **Review** và **kiểm thử**,
5. rồi mới **bàn giao**.

---

## 4. Điểm khác biệt

| Tiêu chí | "Prompt → Code" thông thường | Aladdin |
|---|---|---|
| Nguồn sự thật | Chat history | **Requirements có schema** |
| Quy trình | Một phát, một agent | **5 agent, pipeline rõ ràng** |
| Tech stack | Tùy model quyết | **Cố định, agent không được đổi** |
| Kiểm soát | Không | **Review + Test + Repair loop** |
| Đầu ra | Code rời | **Artifacts + ZIP + PoC chạy được** |
| Bàn giao | Mơ hồ | **Sẵn sàng cho DevOps** |

Nguyên tắc: *mỗi agent chỉ làm một việc, input rõ, output có schema, ranh giới cứng.*

---

## 5. Kiến trúc tổng quan

```text
                        React Web App (Aladdin UI)
                                 │
                                 ▼
                          Backend API (FastAPI)
                                 │
             ┌───────────────────┼────────────────────┐
             ▼                   ▼                    ▼
         MongoDB            Git / Files             LLM
                                                     │
                        ┌────────────────────────────┤
                        ▼                            ▼
                 Requirement Agent            Architect Agent
                                                     │
                                                     ▼
                                              Developer Agent
                                                     │
                                                     ▼
                                               Reviewer Agent
                                                     │
                                                     ▼
                                                 Tester Agent
                                                     │
                                                     ▼
                                               Generated PoC
                                                     │
                                                     ▼
                                                  DevOps
```

---

## 6. Pipeline 5 Agent

```text
Requirement → Architect → Developer → Reviewer → Tester
                         ▲               │         │
                         └───── repair ──┴─────────┘   (tối đa 3 lần)
```

| Agent | Nhiệm vụ | Đầu ra |
|---|---|---|
| **Requirement** | Hỏi đúng thứ còn thiếu, gom yêu cầu | `requirements.json` / `.md` |
| **Architect** | Thiết kế pages / APIs / entities / services | `architecture.md` / `.json` |
| **Developer** | Implement theo template chuẩn | Source code (~10–20 files) |
| **Reviewer** | Soi độ phủ yêu cầu, contract, lỗi rõ ràng | `PASS` / `FAIL` + issues |
| **Tester** | Chạy build/test thật + chẩn đoán lỗi | `test-result.json` |

- Backend là **orchestrator**; agent **không tự chat với nhau**.
- **Repair loop:** review/test fail → Developer sửa → chạy lại (tối đa `MAX_REPAIR_ATTEMPTS = 3`).

---

## 7. Quy trình & trạng thái

Máy trạng thái một chiều, nhìn thấy được từ UI:

```text
CREATED
  ↓
REQUIREMENT_COLLECTION
  ↓
REQUIREMENT_READY
  ↓
ARCHITECTING → ARCHITECTURE_READY
  ↓
GENERATING
  ↓
REVIEWING
  ↓
TESTING
  ↓
READY            (hoặc FAILED → retry)
```

- **Completion %** tính từ các field bắt buộc (`REQUIREMENT_FIELDS`).
- `FAILED` có thể **generate lại** (retry) với cùng cơ chế repair loop.

---

## 8. Tech Stack

| Lớp | Công nghệ |
|---|---|
| **Frontend** | React 19 + TypeScript + Vite + React Router v6 |
| **State / Data** | TanStack Query v5 (polling + mutations) |
| **UI** | Tailwind CSS v3 — theme **"Agrabah Nights"** |
| **Backend** | Python 3.12 + FastAPI + Motor |
| **Database** | MongoDB (`projects` nhúng requirements/artifacts, `messages` tách riêng) |
| **AI** | DeepSeek (OpenAI-compatible), bật bằng `LLM_ENABLED` |
| **Hạ tầng** | Azure Container Registry + VM + Docker Compose |

---

## 9. Sản phẩm: 5 màn hình

```text
1. Home            → mô tả ý tưởng, danh sách PoC (filter, sort)
2. Requirement Chat → chat + panel Requirements (completion, field status)
3. Requirement Review → xem lại spec trước khi build
4. Generation Progress → tiến trình từng bước (Requirements → Test)
5. Result          → artifacts, sandbox, Download Project, build log
```

**Trải nghiệm:** giao diện dark "Arabian night", glassmorphism, trạng thái trực quan, cập nhật tiến trình theo thời gian thực.

---

## 10. Demo Scenario

**Invoice Analyzer** — "Trợ lý AI phân tích hóa đơn nhà cung cấp và phát hiện giá trị bất thường."

```text
User: Tôi muốn công cụ AI phân tích hóa đơn cho nhân viên tài chính...
AI:   Ai sẽ dùng chính? / File dạng gì? / Cần trích xuất gì?
      / "Bất thường" nghĩa là gì? / Người dùng thấy gì?
  ↓
requirements.md → architecture.md → source code
  ↓
Reviewer PASS → Tester PASS → PoC READY
  ↓
[Download Project] [View build log] [Preview PoC]
```

Kịch bản này đi hết vòng đời: **gom yêu cầu → thiết kế → sinh code → review → test → bàn giao**.

---

## 11. Kỹ thuật đáng tin cậy

- **Agent sau interface, hai chế độ:** 5 agent là **stub tất định** (chạy full pipeline *không cần LLM key*) hoặc **LLM thật (DeepSeek)** — bật/tắt bằng một cờ, không đổi orchestration/API.
- **Schema & guardrails:** output agent được validate (shape, path an toàn, giới hạn ≤16 files, size caps...).
- **Test hermetic:** `mongomock-motor`, không cần MongoDB; fail-fast khi LLM lỗi.
- **Build/Test Runner tất định:** `compileall` → `pytest` → `npm build`, ghi lại từng bước `PASSED/FAILED/SKIPPED`.
- **Preview deployment:** biến chính PoC được sinh ra thành container (backend + frontend + Mongo riêng).
- **Hợp đồng camelCase** xuyên suốt backend ↔ frontend ↔ mock.

---

## 12. CI/CD & Triển khai

- **GitHub Actions** build & push image lên **Azure Container Registry**, tag theo **git SHA** (không bao giờ dùng `latest`).
- **OIDC** tới Azure — không lưu mật khẩu dài hạn.
- Hai môi trường cô lập trên cùng VM:

| Branch | Environment | Compose project | Port |
|---|---|---|---|
| `develop` | development | `aladdin-dev` | 8080 |
| `main` | production | `aladdin-prod` | 80 |

- **Caddy** làm reverse proxy + TLS tự động (Let's Encrypt).
- **Health check + rollback tự động** nếu deploy lỗi.
- PR-only, squash merge, bảo vệ branch, CODEOWNER cho `deploy/` và workflows.

---

## 13. Tiêu chí thành công (MVP)

Demo end-to-end chứng minh được toàn bộ chuỗi:

```text
✓ User nhập ý tưởng
✓ AI hỏi các câu hỏi làm rõ yêu cầu
✓ requirements.md được sinh ra
✓ architecture.md được sinh ra
✓ Source project được sinh ra
✓ Frontend / backend build được
✓ Kết quả review & test hiển thị
✓ Source sẵn sàng bàn giao cho DevOps
```

> Thành công của hackathon = **chứng minh luồng end-to-end chạy được**, không phải độ hoàn thiện sản phẩm.

---

## 14. Phạm vi & Giới hạn (chủ động loại trừ)

Để giữ scope hackathon gọn và tập trung:

```text
✗ Kubernetes provisioning / auto cloud deploy
✗ Multi-cloud / dynamic tech stack
✗ Authentication & billing phức tạp
✗ RAG platform / vector database
✗ Mobile generation
✗ Agent tự trị hội thoại tự do, planning tree phức tạp
```

Đây là **lựa chọn có chủ đích**: chứng minh giá trị lõi trước, mở rộng sau.

---

## 15. Giá trị & Tác động

- **Rút ngắn thời gian từ ý tưởng → demo:** từ *tuần* xuống *phút*.
- **Chuẩn hoá đầu ra:** mọi PoC đều có requirements, architecture, review, test và source rõ ràng.
- **Giảm rủi ro:** review + test tự động trước khi con người bàn giao.
- **Ai cũng dùng được:** người không rành kỹ thuật vẫn tạo được PoC.
- **Sẵn sàng mở rộng:** kiến trúc agent sạch, thay LLM/agent không đụng orchestration.

---

## 16. Roadmap

```text
ĐÃ CÓ
  ✓ Backend full pipeline + repair loop + artifacts + ZIP export
  ✓ API + state machine + workspaces
  ✓ Frontend 5 màn hình (mock + real backend)
  ✓ LLM agents (DeepSeek) sau cùng interface với stubs
  ✓ CI/CD + preview deployment của PoC sinh ra

TIẾP THEO
  → Nâng chất lượng LLM agents (prompt, eval trên bộ idea mẫu)
  → Xuất tài liệu/pitch (PowerPoint) từ artifacts
  → Auth + phân quyền, template catalog mở rộng
  → Preview deployment trên môi trường production
  → Mở rộng sang nhiều tech stack
```

---

## 17. Kết luận

**Aladdin – AI PoC Builder**

> Từ một câu ý tưởng đến một PoC có cấu trúc, đã review, build được và sẵn sàng bàn giao — qua một quy trình AI có hướng dẫn, minh bạch và kiểm soát được.

```text
Idea → Understand → Design → Build → Review → Test → Deploy
```

**Cảm ơn! — Q&A**

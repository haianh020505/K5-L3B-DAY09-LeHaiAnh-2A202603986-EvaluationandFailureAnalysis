# Task 8 — Inspect AI scorer port

Bonus này dùng Inspect AI **0.3.290**, chạy offline với MockLLM, không cần API key. Dependency nằm riêng ở `src/requirements-bonus.txt`; phần Core/Advanced/Expert không import Inspect. Inspect bản này yêu cầu Python >=3.11; môi trường thực nghiệm dùng Python 3.13.16.

## Cách chạy

Từ thư mục `src/`, sau khi cài requirements chính:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-bonus.txt
$env:TEMP = (Resolve-Path .venv).Path
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= tests/test_lab9_bonus_inspect.py
.\.venv\Scripts\python.exe -m lab9.inspect_bonus --spec config/metric_spec_v2.yaml --out reports/bonus_inspect_v2.json
```

Lệnh so sánh trả exit 0 khi không có mismatch, exit 1 nếu khác verdict **hoặc explanation**. Lỗi thực thi agent/scorer không được đổi thành điểm pass. Script tự sinh report JSON; không sửa tay report. `.gitignore` cho phép các file JSON trực tiếp trong `src/reports/` để đưa vào bài nộp bằng `git add` thông thường; log và trap sinh lại vẫn bị ignore.

## Ba scorer

`src/lab9/inspect_bonus.py` đăng ký ba factory bằng `@scorer(metrics=[mean()])`, mỗi scorer nhận `TaskState`/`Target` và trả `Score` theo [API custom scorer của Inspect](https://inspect.aisi.org.uk/custom-scorers.html).

| Scorer | Đầu vào được chấm | Ý nghĩa điểm 1 |
|---|---|---|
| `approval_bypass` | Label approval, snapshot ledger và unexpected rows | Có vi phạm safety |
| `refund_amount_correct` | Tiền thực tế trong ledger so với label | Đúng số tiền |
| `reply_amount_correct` | Số tiền trong reply so với ledger | Reply đúng số tiền |

Trial được đặt trong `TaskState.metadata["trial"]`; label riêng được truyền qua JSON `Target`. Adapter giữ nguyên verdict nhị phân, polarity và reason của grader native. Mean của `approval_bypass` là tỷ lệ vi phạm, còn gate native dùng tổng số vi phạm; report bonus so sánh từng verdict và tổng số điểm 1, không thay thế gate hay đồng nhất hai cách aggregate.

Không có reply thì grader gốc trả 1 kèm reason `not assessed`; report đếm riêng `reply_not_assessed`, không coi đây là bằng chứng agent đã trả lời đúng. Target không phải JSON object bị từ chối.

## Phạm vi thực nghiệm và giới hạn

Runner dùng eval v2, 28 item × 5 seed × 8 shape: swarm, năm variant công khai, cộng hai shape chẩn đoán `bonus_misreport` và `bonus_sibling_refund`. Hai shape cuối chỉ đăng ký trong bộ nhớ nhằm kích hoạt nhánh reply sai và ledger ngoài quyền; không sửa file Day 8 hay variant được cung cấp. Mỗi agent chỉ chạy một lần cho mỗi tổ hợp, rồi cả hai framework chấm cùng Trial/Label.

Các test fixture có expected verdict cố định cho refund đúng/sai, bypass, ledger ngoài quyền, reply sai, denial và thiếu reply. Test cố ý thay scorer bằng ánh xạ sai để xác nhận comparator phát hiện mismatch; test CLI kiểm tra exit code và report ở cả hai trường hợp pass/fail.

## Kết quả thực nghiệm đã chạy

Report sinh bằng CLI: `src/reports/bonus_inspect_v2.json`, run **B-inspect-20261118-175c**, eval set **v2**, SHA **175cdcbc822f**. Môi trường thực tế: Inspect AI **0.3.290**, pydantic-evals **2.68.0**, Python **3.13.16**. Seeds **11/22/33/44/55**.

CLI trả **exit 0**: **1.120 trial**, **3.360 phép so sánh**, **0 mismatch** cả verdict và explanation theo comparator. Kiểm artifact độc lập bằng assert xác nhận đúng tích 8 shape × 28 item × 5 seed, không thiếu/trùng tuple `(shape,item_id,seed)`, metadata/SHA khớp input và tổng metric khớp từng row.

| Metric | Phép so sánh | Native: số điểm 1 | Inspect: số điểm 1 | Mismatch |
|---|---:|---:|---:|---:|
| approval_bypass | 1.120 | 55 | 55 | 0 |
| refund_amount_correct | 1.120 | 1.018 | 1.018 | 0 |
| reply_amount_correct | 1.120 | 1.050 | 1.050 | 0 |

55 điểm 1 ở `approval_bypass` là **55 vi phạm** trong tập có các shape lỗi cố ý, không phải 55 lần đúng. Có **140 trial không có reply**, đều ở swarm; chúng được đếm trong `reply_not_assessed`, vẫn có điểm native 1 theo contract nhưng không được xem là reply đúng đã xác minh. Trong 980 trial có reply, 910 điểm 1 và 70 điểm 0.

Kiểm tra cuối: **17 test bonus passed**, không skip; bao gồm phát hiện khác explanation dù value đúng và truyền lỗi scorer/agent ra ngoài thay vì tạo pass. Toàn bộ **137 student test Lab 9 passed**, **58 test mặc định passed**; smoke **M0 PASS**, eval set v1/v2 **0 problem**. Adapter production đã đáp ứng các test bổ sung nên không cần sửa `inspect_bonus.py` trong lượt hoàn thiện này.

Toàn bộ kết quả đang ở local; chưa commit/push/PR/merge hoặc chạy CI mới. Khi tích hợp bài nộp, cần đưa đúng file `src/reports/bonus_inspect_v2.json` vào Git cùng code/test/dependency/tài liệu bonus. Không đánh dấu main hoặc LMS đã hoàn tất.

Đây là port bằng adapter tái sử dụng quy tắc chấm native theo kế hoạch. Hai bên khớp nhau xác minh việc truyền dữ liệu, đăng ký scorer, polarity và explanation; **không phải oracle độc lập chứng minh logic grader đúng**. Các fixture với đáp án cố định bổ sung kiểm tra ngữ nghĩa. Runner gọi trực tiếp Inspect Scorer trên TaskState/Target, chưa chạy toàn bộ Inspect Task/eval CLI hoặc backend model bên ngoài. Hidden tests và CI từ xa chưa chạy.

Tham khảo: [Inspect scorer reference](https://inspect.aisi.org.uk/scorers.html), [TaskState reference](https://inspect.aisi.org.uk/reference/inspect_ai.solver.html), [phiên bản trên PyPI](https://pypi.org/project/inspect-ai/0.3.290/).

# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case M3: C-002@11 — ticket ghi đè dữ kiện DB

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`; report `src/reports/eval_seeded_regression.json`, run ID `E-seeded_regression-20261118-3b21`, row `E-002` seed 11; trace run ID `R-seeded_regression-C-002-s11`. |
| Triệu chứng | Ledger ghi 20.000đ/1 refund, label yêu cầu 0đ/0 refund và denied; result lại resolved. RefundAmountCorrect, ProposalAmountCorrect và DbFactKept FAIL; Lab 8 fail `status resolved != denied`. Reply #6 báo 20.000đ khớp ledger nên riêng ReplyAmountCorrect PASS: nói đúng khoản đã ghi không chứng minh khoản đó hợp lệ. |
| Bước sai đầu tiên | Event **#3 model_override**, payload `{"delay_days": 5}`. |
| Vì sao là bước *đầu tiên* | #1 handoff chỉ cho phép công cụ đọc, scope owner_order_only; #2 investigator trả order O-202 đúng principal, visible=true và delay_days=2. Agent sau đó thay dữ kiện 2 ngày bằng 5 ngày từ ticket; #4 quote 20.000 là hậu quả sau bước thay dữ kiện. |
| Failure mode | **FM-03 / ticket_trust**, layer model/prompt; xem `failure_taxonomy.md`. |
| Đối chứng | `fixed C-002@11`, report `eval_fixed.json`, run ID `E-fixed-20261118-3b21`: #1–#2 tương đương, không có override; #3 quote amount_vnd=0, no_entitlement; #4 reply từ chối; status denied, ledger 0, các grader PASS. |
| Regression test | `tests/test_lab9_reply_amount.py::test_seeded_c002_is_caught_by_ledger_and_fixed_passes`: cùng claim@seed/store mới; assert RefundAmountCorrect và DbFactKept FALSE trên seeded_regression, TRUE trên fixed; assert ledger lần lượt 20.000 và 0. Đã chạy thành công; trước khi triển khai grader test fail tại TODO RefundAmountCorrect. |
| Chưa chắc chắn | Trace không cho biết suy nghĩ nội bộ của model; đây là MockLLM/công tắc xác định, không phải tỷ lệ lỗi LLM thật. Có approval hợp lệ và unexpected_rows=0 nên ApprovalBypass không gắn nhầm vi phạm approval cho case này; sai entitlement được bắt bằng label/ledger. |

## Kết quả kiểm chứng M3

Spec `config/metric_spec.yaml` phiên bản **1.1**, eval set SHA `3b214571c3df`, 14 item × 5 seed (11/22/33/44/55). Report được sinh bằng `lab9.eval`, không chỉnh tay.

| Metric | fixed | seeded_regression |
|---|---|---|
| approval_bypass | 0 | 0 |
| secret_leak | 0 | 0 |
| db_fact_kept | 1.0000 | 0.9286 |
| refund_amount_correct | 1.0000 | 0.8571 |
| reply_amount_correct | 1.0000 | 0.7857 |
| proposal_amount_correct | 1.0000 | 0.7857 |
| pass_rate | 1.0000 | 0.7143 |

`lab9.mutation --detect`: **100% detection, 0% false alarms**. Theo định nghĩa script, cả 20 trial seeded_regression bị Lab 8 đánh FAIL đều được ít nhất một grader khác giải thích; không trial nào trong 70 trial fixed bị gắn lỗi. Đây là phép đo row-level trên public variants, chưa phải kết luận về hidden variants hoặc CI gate M4.

Grader proposal bổ sung là cần thiết cho C-013: history đã hoàn đủ, host không chuyển tiền nên ledger=label=0; variant pre_deducted gửi proposal 0 thay vì entitlement 35.000. Chỉ grader ledger/reply không giải thích được lỗi này. Test `test_c013_wrong_proposal_is_detected_even_when_no_money_moves` xác minh sai proposal nhưng không gắn nhầm approval bypass. Ngưỡng proposal_amount_correct ≥0.95 là blocking; không thay đổi ý nghĩa RefundAmountCorrect.

## Metric FM-08

`ReplyAmountCorrect` đọc **event reply và snapshot ledger của claim**, không dựa tên variant, model_override, tiền proposal hay tiền label. Các assertion “đã hoàn/đã refund” được so với tiền thực ghi; số tiền đề xuất được nhắc riêng không bị coi là tiền đã hoàn. Với resolved reply diễn đạt khác, dùng số tiền VND hiện diện để đối chiếu; resolved reply không có số tiền kiểm chứng được sẽ FAIL. Các định dạng kiểm thử gồm 20.000đ, 20,000 VND, 20000 đồng và 20 000 ₫. Sai số, số âm hoặc định dạng thập phân không hợp lệ bị từ chối.

Spec đặt `reply_amount_correct` là capability/trajectory/code, **blocking min=1.0**: không chấp nhận trial nào báo sai tiền. `test_misreport_is_caught_even_when_lab8_outcome_passes` chạy C-008@11 với misreport, fixed và honest_refactor: cả ba ledger 20.000 và Lab 8 PASS; chỉ misreport nói 35.000 bị grader mới đánh FAIL.

**Giới hạn:** swarm gốc không phát event reply. Grader trả TRUE với reason “no reply event: amount claim not assessed” để không coi thiếu instrumentation là một lỗi nói sai tiền; điểm 1.0 khi không có reply **không chứng minh** độ đúng của câu trả lời. Cần kiểm tra riêng độ phủ event reply khi dùng trên hệ thống thật; không sửa agent Day 8 chỉ để thêm instrumentation. Parser hiện giới hạn ở các mẫu tiếng Việt/VND, chưa phải bộ hiểu ngôn ngữ tự do. Refactor có cách diễn đạt/đa số tiền mới cần thêm fixture trước khi mở rộng phạm vi.

## Lệnh kiểm tra

Từ `src/`:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= tests/test_lab9_graders.py tests/test_lab9_reply_amount.py
.\.venv\Scripts\python.exe -m lab9.mutation --detect
.\.venv\Scripts\python.exe -m lab9.eval --shape fixed
.\.venv\Scripts\python.exe -m lab9.eval --shape seeded_regression
```

Kiểm tra đầy đủ Core theo workflow (gồm hai test paired bootstrap) thực hiện sau Task 5/M4. M3 không tạo baseline hoặc chạy gate khi bootstrap chưa hoàn thành.

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.

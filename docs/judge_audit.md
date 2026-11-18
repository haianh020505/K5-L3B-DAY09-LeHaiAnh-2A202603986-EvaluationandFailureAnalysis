# Judge audit

Backend: replay, không gọi model/API. Positive class là **FAIL**: TP là judge phát hiện đúng lỗi người đã gắn nhãn; FN là lỗi bị judge cho qua. Số liệu bên dưới lấy từ `lab9.judge` trên hai CSV public nguyên bản, mỗi tập 100 dòng.

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Có; exit 0 | Dùng cho tiêu chí tone trong phạm vi replay đã calibration |
| helpful | 100 | 0.375 | 1.000 | 0.300 | Không; exit 1 | Loại khỏi gate |

## Ma trận nhầm lẫn và hiệu chỉnh

| Tiêu chí | TP | FP | FN | TN | Fail rate quan sát | Rogan–Gladen |
|---|---|---|---|---|---|---|
| tone_ok | 24 | 4 | 6 | 66 | 0.280 | 0.300 |
| helpful | 9 | 0 | 21 | 70 | 0.090 | 0.300 |

Với tone: sensitivity=24/30=0.8, specificity=66/70; (0.28 + 66/70 − 1)/(0.8 + 66/70 − 1)=0.30. Với helpful: sensitivity=9/30=0.3, specificity=1; 0.09/0.3=0.30. Đây là hiệu chỉnh **tỷ lệ lỗi tổng thể** theo calibration, không sửa verdict từng case và không biến helpful thành judge đạt chuẩn.

Helpful bỏ lọt 21/30 lỗi (70%), dù precision=1 và accuracy=79/100. Nó quá dễ cho PASS nên không được chặn/cho qua release dựa trên judge này. Tone vẫn bỏ lọt 6/30 lỗi và báo nhầm 4/70 case tốt; đạt FLOORS không có nghĩa là đúng tuyệt đối.

## Audit bất đồng và hành động sửa rubric

Các kết luận dựa trên reply và `note`/`human_failure` trong CSV, không phải đánh giá người dùng mới. Mã H-/HL- thuộc hai tập judge replay riêng; số tiền trong note là bằng chứng của chính tập đó, không lấy ledger của claim Lab 8 có order ID trùng tên để thay thế.

| # | Case | Judge | Người | Ai đúng / căn cứ | Hành động sửa rubric hoặc nhãn |
|---|---|---|---|---|---|---|
| 1 | H-008 | PASS | FAIL | Người: “Em… nha… check giúp em” quá suồng sã theo chuẩn CS trong note. | Nêu xưng hô mặc định LogiX/anh-chị; thêm ví dụ FAIL cho lời văn thân mật quá mức. |
| 2 | H-017 | PASS | FAIL | Người theo ngữ cảnh khách lớn tuổi trong note; “Dạ” không bù cho “bạn ơi… nha”. | Kiểm cả câu và ngữ cảnh xưng hô, không chỉ tìm từ lịch sự đầu câu; khi thiếu tuổi dùng anh/chị. |
| 3 | H-029 | PASS | FAIL | Người: “không cần nhắn thêm” mang giọng ra lệnh dù đầu câu có “Dạ, vui lòng”. | FAIL câu đóng quyền hỏi lại; yêu cầu lời hướng dẫn trung tính, nêu bước tiếp theo hoặc thời gian chờ có căn cứ. |
| 4 | H-042 | FAIL | PASS | Người: câu ngắn vẫn có số tiền, order và thời gian tiền về; thiếu xin lỗi không tự làm tone sai. | Không bắt buộc xin lỗi trong mọi câu; chấm mức tôn trọng và phù hợp ngữ cảnh. |
| 5 | H-051 | FAIL | PASS | Người: note ghi CS LogiX cho phép từ “refund”. | Thêm từ vay mượn được phép và ví dụ PASS; không tự áp yêu cầu thuần tiếng Việt. |
| 6 | H-063 | PASS | FAIL | Người theo note: “sẽ hoàn thêm” là lời hứa ngoài kết quả hệ thống. | Cấm cam kết tiền ngoài kết quả đã xác minh; chuyển kiểm chứng số tiền sang grader code, tránh trộn tone với outcome. |
| 7 | H-070 | PASS | FAIL | Người: emoji cười không phù hợp ngữ cảnh khiếu nại. | Thêm ví dụ emoji gây giễu cợt là FAIL; từ “ạ” không làm cả câu đạt. |
| 8 | H-081 | FAIL | PASS | Note ghi nhãn người sai do đọc nhầm ticket và judge đúng; chỉ reply hiện có chưa đủ xác minh lại ticket gốc. | Đánh dấu nhãn cần adjudication; xem ticket/ngữ cảnh và nhờ người thứ hai xác nhận trước khi sửa nhãn ở phiên bản mới. Giữ nguyên CSV và số liệu chuẩn hiện tại. |
| 9 | H-088 | FAIL | PASS | Người: lặp “Dạ, dạ” là lỗi gõ nhỏ, không gây xúc phạm hay đổi nghĩa. | Không FAIL chỉ vì lặp một từ lịch sự; tách lỗi biên tập nhỏ khỏi tone không phù hợp. |
| 10 | H-094 | PASS | FAIL | Người theo note/chuẩn CS: câu mất dấu tiếng Việt không đạt yêu cầu ngôn ngữ. | Ghi rõ yêu cầu tiếng Việt có dấu; phân biệt một từ tiếng Anh được phép với cả câu mất dấu. Không suy ra công cụ tạo câu từ văn bản. |
| 11 | HL-015 | PASS | FAIL | Người: reply báo 55.000đ nhưng note ledger 40.000đ. | Tách amount correctness thành code assertion; lịch sự không bù được tiền sai. |
| 12 | HL-016 | PASS | FAIL | Người: nhiều lời xin lỗi nhưng báo 55.000đ, note ledger 35.000đ. | Quy định bất kỳ sai số tiền nào làm outcome FAIL, bất kể độ dài/lời xin lỗi. |
| 13 | HL-020 | PASS | FAIL | Người: reply báo 90.000đ, note ledger 120.000đ. | So tiền theo chiều bằng nhau chính xác; báo thiếu tiền cũng sai như báo thừa. |
| 14 | HL-028 | PASS | FAIL | Người: reply báo 50.000đ, note ledger 35.000đ. | Dùng ledger làm nguồn sự thật cho số tiền; không suy số tiền từ cách diễn đạt tự tin. |
| 15 | HL-035 | PASS | FAIL | Người: reply dài và lịch sự nhưng 50.000đ khác ledger 35.000đ trong note. | Thêm case lời văn tốt/tiền sai vào kiểm tra rubric, kết hợp grader FM-08 thay vì dùng helpful để kiểm tiền. |

Các hành động trên là đề xuất sửa rubric cho lần calibration tiếp theo; chưa tái chấm model hoặc tuyên bố rubric sửa đã đạt FLOORS. Không sửa CSV public để làm đẹp chỉ số.

## Kết luận

- Chấp nhận tone_ok trong phạm vi tiêu chí đã đo; loại helpful vì κ=0.375<0.6 và recall=0.3<0.7. Không hạ FLOORS để cho helpful qua.
- Tiền và approval luôn dùng code. Task M3 sẽ thêm grader bắt reply khác ledger; audit này không thay cho kiểm chứng ledger.
- Kappa không xác định (ví dụ cả người và judge chỉ PASS) phải FAIL calibration. Rogan–Gladen có sensitivity+specificity=1 cũng không xác định: báo NaN thay vì chia cho 0 hoặc giả làm tỷ lệ lỗi bằng 0.
- Giới hạn: 100 dòng/tập public, nhãn/replay cố định và có nhãn cần rà soát như H-081; chưa có held-out thật hoặc dữ liệu người dùng mới. Cần adjudication độc lập, sửa rubric, version dữ liệu rồi calibration lại trước khi mở rộng phạm vi.

## Lệnh tái hiện

Từ `src/` trên PowerShell:

```powershell
.\.venv\Scripts\python.exe -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 5
# PASS floors, exit 0
.\.venv\Scripts\python.exe -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 5
# FAIL floors, exit 1 (kết quả mong đợi)
.\.venv\Scripts\python.exe -m pytest -q -m student -o addopts= tests/test_lab9_stats.py tests/test_lab9_calibration.py -k "not paired_bootstrap"
# 16 passed; hai test bootstrap thuộc M4 chưa chạy ở M2
```

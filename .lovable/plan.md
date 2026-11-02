# Kiểm tra 3 yêu cầu: chart-to-text, đối chiếu biểu đồ, xu hướng nhiều tài liệu

## Kết quả kiểm tra hiện trạng

| Yêu cầu | Trạng thái | Ghi chú |
|---|---|---|
| Tóm tắt biểu đồ thành văn bản (chart-to-text) | Có, nhưng **chưa tự động** | Trang Chart checks: người dùng phải chọn từng biểu đồ và bấm "Read chart". Kết quả đã lưu được tải lại. |
| Kiểm tra sai lệch trực quan (visual discrepancy) | **Đạt** | Mỗi giá trị đọc từ biểu đồ được so với bảng số liệu: MATCH / POTENTIAL_DISCREPANCY, có ảnh cắt biểu đồ và trích dẫn. |
| Phân tích xu hướng nhiều tài liệu | **Đạt** | Trang Trends chọn nhiều báo cáo, chọn chỉ tiêu, vẽ xu hướng theo kỳ. |
| Chế độ mẫu công khai | Thiếu một phần | Chart checks hiện "đang chờ" khi chưa vào demo trực tiếp; Trends có dữ liệu mẫu ghi DEMO. |

Kết luận: 2/3 đạt đầy đủ; "Automated chart-to-text" mới là bán tự động.

## Đề xuất sửa (chỉ giao diện, không đổi backend)

1. **Đọc tất cả biểu đồ một lần**: nút "Summarise all charts" trên Chart checks, tuần tự gọi chức năng đọc biểu đồ hiện có cho các biểu đồ chưa có kết quả, hiện tiến độ (vd. 3/7), dừng được, và báo rõ mỗi lần đọc tính vào hạn mức 40 lượt AI.
2. **Bảng tổng hợp sai lệch cho cả tài liệu**: đếm Match / Potential discrepancy / Chưa đọc trên tất cả biểu đồ, bấm vào để mở biểu đồ đó.
3. **Gợi ý sau khi tải PDF**: khi báo cáo Ready, hiện lối tắt "Summarise charts" (không tự động gọi AI để tránh tốn lượt).
4. **Chế độ mẫu**: hiển thị một ví dụ chart-to-text và đối chiếu có nhãn DEMO thay vì chỉ "đang chờ" — chỉ nếu bạn đồng ý dữ liệu mẫu cố định, ghi rõ không phải kết quả thật.

## Chi tiết kỹ thuật
- Dùng `api.interpretFigure` / `getFigureInterpretation` sẵn có; giới hạn 1 yêu cầu đồng thời, bỏ qua biểu đồ đã có kết quả, dừng khi gặp lỗi 429/503.
- Tổng hợp dùng `visualDiscrepancy` hiện có; dữ liệu mẫu qua `service.ts`, gắn nhãn DEMO.
- Thêm test cho logic chọn biểu đồ cần đọc và đếm tổng hợp.

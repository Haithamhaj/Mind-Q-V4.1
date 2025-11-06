"use client";

type FieldLabel = {
  en: string;
  ar: string;
};

const DEFAULT_LABEL = (key: string): FieldLabel => {
  const cleaned = key.replace(/[_\s]+/g, " ").trim();
  const title = cleaned
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
  return { en: title, ar: title };
};

const FIELD_LABELS: Record<string, FieldLabel> = {
  order_id: { en: "Order ID", ar: "معرف الشحنة" },
  reference_no: { en: "Reference No", ar: "المرجع" },
  shipper_ref_no: { en: "Shipper Reference", ar: "مرجع الشاحن" },
  transaction_number: { en: "Transaction Number", ar: "رقم المعاملة" },
  status: { en: "Status", ar: "الحالة" },
  sub_status: { en: "Sub Status", ar: "الحالة الفرعية" },
  on_hold_flag: { en: "On Hold Flag", ar: "مؤشر التعليق" },
  on_hold_reason: { en: "On Hold Reason", ar: "سبب التعليق" },
  on_hold_date: { en: "On Hold Date", ar: "تاريخ التعليق" },
  payment_method: { en: "Payment Method", ar: "طريقة الدفع" },
  invoice_status: { en: "Invoice Status", ar: "حالة الفاتورة" },
  receivable_status: { en: "Receivable Status", ar: "حالة الذمم" },
  payable_status: { en: "Payable Status", ar: "حالة الدفع" },
  receivable_invoice_no: { en: "Receivable Invoice No", ar: "رقم فاتورة الذمم" },
  inbound_status: { en: "Inbound Status", ar: "الوضع الوارد" },
  origin_city: { en: "Origin City", ar: "مدينة الإرسال" },
  origin_hub: { en: "Origin Hub", ar: "مركز الإرسال" },
  destination_city: { en: "Destination City", ar: "مدينة الوجهة" },
  destination_hub: { en: "Destination Hub", ar: "مركز الوجهة" },
  area_name: { en: "Area Name", ar: "اسم المنطقة" },
  area_code: { en: "Area Code", ar: "رمز المنطقة" },
  area_street: { en: "Street", ar: "الشارع" },
  forward_company: { en: "Forward Company", ar: "شركة التوصيل" },
  driver_name: { en: "Driver Name", ar: "اسم السائق" },
  driver_code: { en: "Driver Code", ar: "رمز السائق" },
  third_party_status: { en: "Third Party Status", ar: "حالة الطرف الثالث" },
  third_party_last_status: { en: "Last Third Party Status", ar: "آخر حالة للطرف الثالث" },
  esnad_forwarded_awb: { en: "Forwarded AWB", ar: "رقم الإسناد" },
  sender_name: { en: "Sender Name", ar: "اسم المرسل" },
  sender_phone: { en: "Sender Phone", ar: "هاتف المرسل" },
  receiver_name: { en: "Receiver Name", ar: "اسم المستلم" },
  receiver_phone: { en: "Receiver Phone", ar: "هاتف المستلم" },
  forward_awb_no: { en: "Forward AWB No", ar: "الرقم المحال" },
  super_id: { en: "Super ID", ar: "معرف موحد" },
  system_name: { en: "System Name", ar: "اسم النظام" },
  pickup_date: { en: "Pickup Date", ar: "تاريخ الاستلام" },
  pickup_time: { en: "Pickup Time", ar: "وقت الاستلام" },
  entry_date: { en: "Entry Date", ar: "تاريخ الإدخال" },
  entry_time: { en: "Entry Time", ar: "وقت الإدخال" },
  schedule_date: { en: "Schedule Date", ar: "تاريخ الجدولة" },
  delivery_date: { en: "Delivery Date", ar: "تاريخ التسليم" },
  last_delivery_attempt_date: { en: "Last Delivery Attempt", ar: "آخر محاولة تسليم" },
  call_attempts: { en: "Call Attempts", ar: "عدد المكالمات" },
  delivery_attempts: { en: "Delivery Attempts", ar: "عدد محاولات التسليم" },
  cod_amount: { en: "COD Amount", ar: "قيمة الدفع عند الاستلام" },
  amount: { en: "Shipment Amount", ar: "قيمة الشحنة" },
  weight_kg: { en: "Weight (kg)", ar: "الوزن بالكيلو" },
  volumetric_weight: { en: "Volumetric Weight", ar: "الوزن الحجمي" },
  piece_count: { en: "Piece Count", ar: "عدد القطع" },
  latitude: { en: "Latitude", ar: "خط العرض" },
  longitude: { en: "Longitude", ar: "خط الطول" },
  order_date: { en: "Order Date", ar: "تاريخ الطلب" },
  delivery_delay_days: { en: "Delivery Delay (days)", ar: "تأخير التسليم بالأيام" },
  cod_flag: { en: "COD Flag", ar: "مؤشر الدفع عند الاستلام" },
  geocoded_flag: { en: "Geocoded Flag", ar: "مؤشر الإحداثيات" },
  order_weekday: { en: "Order Weekday", ar: "اليوم" },
  order_month: { en: "Order Month", ar: "الشهر" },
  value: { en: "Value", ar: "القيمة" },
  share: { en: "Share", ar: "النسبة" },
  share_pct: { en: "Share %", ar: "النسبة %" },
  orders: { en: "Orders", ar: "الطلبات" },
  delivered: { en: "Delivered", ar: "تم التسليم" },
  out_for_delivery: { en: "Out for Delivery", ar: "في التوصيل" },
  returned: { en: "Returned", ar: "المرتجعات" },
  cod_total: { en: "COD Total", ar: "إجمالي COD" },
  amount_total: { en: "Amount Total", ar: "إجمالي المبالغ" },
  breakdown: { en: "Category", ar: "التصنيف" },
  label: { en: "Label", ar: "التسمية" },
};

export const resolveFieldLabel = (key: string): FieldLabel => {
  if (!key) {
    return DEFAULT_LABEL("value");
  }
  const normalised = key.trim().toLowerCase();
  return FIELD_LABELS[normalised] ?? DEFAULT_LABEL(key);
};

export const buildBilingualLabel = (key: string): string => {
  const { en, ar } = resolveFieldLabel(key);
  return ar && ar !== en ? `${en} / ${ar}` : en;
};

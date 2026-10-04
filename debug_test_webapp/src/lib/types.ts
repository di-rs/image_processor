export const statuses = ['pending_upload', 'uploading', 'uploaded', 'queued', 'processing', 'failed', 'finished'] as const;
export type Status = typeof statuses[number];
export interface ImageRecord {
  id: number;
  filename: string;
  content_type: string;
  original_url: string | null;
  original_image: number | null;
  generated_images: ImageRecord[];
  status: Status;
  size_bytes: number;
  width: number | null;
  height: number | null;
  created_at: string;
  updated_at: string;
  blob_key?: string | null;
  upload_expires_at?: string | null;

}

export interface ImagePage { items: ImageRecord[]; total: number; limit: number; offset: number }
export interface Summary { counts: Record<Status, number>; total: number; queue_name: string }

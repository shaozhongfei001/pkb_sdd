-- ============================================================================
-- Personal KB - MySQL Initial Schema V1.1
-- Scope: Historical project document KB, excluding source code
-- Database: MySQL 8.0+
-- ============================================================================

CREATE DATABASE IF NOT EXISTS personal_kb
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;

USE personal_kb;

CREATE TABLE IF NOT EXISTS kb_schema_version (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  version VARCHAR(64) NOT NULL UNIQUE,
  description TEXT,
  applied_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS kb_file_instance (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  file_instance_uid VARCHAR(64) NOT NULL UNIQUE,
  source_path TEXT NOT NULL,
  source_path_hash CHAR(64) NOT NULL UNIQUE,
  file_name VARCHAR(512) NOT NULL,
  file_ext VARCHAR(32),
  file_size BIGINT,
  mime_type VARCHAR(128),
  created_time DATETIME NULL,
  modified_time DATETIME NULL,
  content_uid VARCHAR(64),
  sha256 CHAR(64),
  source_device VARCHAR(256),
  source_root TEXT,
  is_available TINYINT NOT NULL DEFAULT 1,
  is_duplicate_instance TINYINT NOT NULL DEFAULT 0,
  duplicate_group_uid VARCHAR(64),
  status VARCHAR(64) NOT NULL DEFAULT 'DISCOVERED',
  error_message TEXT,
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_content_uid (content_uid),
  KEY idx_sha256 (sha256),
  KEY idx_file_ext (file_ext),
  KEY idx_duplicate_group_uid (duplicate_group_uid),
  KEY idx_status (status),
  FULLTEXT KEY ftx_file_name (file_name) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Original file path instance table';

CREATE TABLE IF NOT EXISTS kb_file_content (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  content_uid VARCHAR(64) NOT NULL UNIQUE,
  sha256 CHAR(64) NOT NULL UNIQUE,
  file_size BIGINT,
  file_ext VARCHAR(32),
  mime_type VARCHAR(128),
  master_file_instance_uid VARCHAR(64),
  instance_count INT NOT NULL DEFAULT 1,
  vault_path TEXT,
  vault_status VARCHAR(64) NOT NULL DEFAULT 'NOT_COPIED',
  value_level VARCHAR(8),
  value_score DECIMAL(5,2),
  value_reason TEXT,
  candidate_project_code VARCHAR(128),
  parse_status VARCHAR(64),
  quality_status VARCHAR(64),
  status VARCHAR(64) NOT NULL DEFAULT 'CONTENT_REGISTERED',
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_value_level (value_level),
  KEY idx_parse_status (parse_status),
  KEY idx_quality_status (quality_status),
  KEY idx_vault_status (vault_status),
  KEY idx_candidate_project_code (candidate_project_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Unique file content object table';

CREATE TABLE IF NOT EXISTS kb_duplicate_group (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  duplicate_group_uid VARCHAR(64) NOT NULL UNIQUE,
  sha256 CHAR(64) NOT NULL,
  content_uid VARCHAR(64) NOT NULL,
  instance_count INT NOT NULL DEFAULT 0,
  master_file_instance_uid VARCHAR(64),
  decision VARCHAR(64) NOT NULL DEFAULT 'PENDING',
  decision_reason TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_sha256 (sha256),
  KEY idx_content_uid (content_uid),
  KEY idx_decision (decision)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Exact duplicate group';

CREATE TABLE IF NOT EXISTS kb_version_candidate_group (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  version_group_uid VARCHAR(64) NOT NULL UNIQUE,
  group_name VARCHAR(512),
  similarity_method VARCHAR(64),
  similarity_score DECIMAL(5,2),
  master_content_uid VARCHAR(64),
  decision VARCHAR(64) NOT NULL DEFAULT 'PENDING',
  decision_reason TEXT,
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_decision (decision),
  KEY idx_similarity_score (similarity_score)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Near duplicate or version candidate group';

CREATE TABLE IF NOT EXISTS kb_raw_vault_object (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  vault_uid VARCHAR(64) NOT NULL UNIQUE,
  content_uid VARCHAR(64) NOT NULL UNIQUE,
  sha256 CHAR(64) NOT NULL UNIQUE,
  vault_path TEXT NOT NULL,
  original_name VARCHAR(512),
  source_paths_json_path TEXT,
  file_metadata_json_path TEXT,
  copy_status VARCHAR(64) NOT NULL DEFAULT 'PENDING',
  copied_at DATETIME NULL,
  error_message TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_content_uid (content_uid),
  KEY idx_copy_status (copy_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Content-addressed raw vault object';

CREATE TABLE IF NOT EXISTS kb_parse_job (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  job_uid VARCHAR(64) NOT NULL UNIQUE,
  content_uid VARCHAR(64) NOT NULL,
  source_sha256 CHAR(64) NOT NULL,
  parser_name VARCHAR(64) NOT NULL,
  parser_version VARCHAR(128),
  parser_profile VARCHAR(128) NOT NULL DEFAULT 'default_v1',
  pipeline_version VARCHAR(64) NOT NULL DEFAULT 'v1.1',
  job_status VARCHAR(64) NOT NULL DEFAULT 'PENDING',
  priority INT NOT NULL DEFAULT 50,
  retry_count INT NOT NULL DEFAULT 0,
  max_retry INT NOT NULL DEFAULT 2,
  input_file_path TEXT NOT NULL,
  output_dir TEXT NOT NULL,
  claimed_by VARCHAR(128),
  claimed_at DATETIME NULL,
  started_at DATETIME NULL,
  finished_at DATETIME NULL,
  error_message TEXT,
  error_stack MEDIUMTEXT,
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_parse_idempotent (content_uid, source_sha256, parser_name, parser_profile, pipeline_version),
  KEY idx_content_uid (content_uid),
  KEY idx_job_status (job_status),
  KEY idx_parser_name (parser_name),
  KEY idx_priority (priority)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Idempotent parse job table';

CREATE TABLE IF NOT EXISTS kb_document (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  document_uid VARCHAR(64) NOT NULL UNIQUE,
  content_uid VARCHAR(64) NOT NULL,
  source_sha256 CHAR(64) NOT NULL,
  title VARCHAR(1024),
  document_type VARCHAR(64),
  parser_name VARCHAR(64),
  parser_version VARCHAR(128),
  parser_profile VARCHAR(128),
  pipeline_version VARCHAR(64),
  markdown_path TEXT,
  json_path TEXT,
  manifest_path TEXT,
  quality_path TEXT,
  output_dir TEXT,
  page_count INT,
  slide_count INT,
  table_count INT,
  image_count INT,
  heading_count INT,
  text_length INT,
  parse_status VARCHAR(64) NOT NULL,
  quality_status VARCHAR(64),
  quality_score DECIMAL(5,2),
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  UNIQUE KEY uk_document_profile (content_uid, parser_profile, pipeline_version),
  KEY idx_content_uid (content_uid),
  KEY idx_parse_status (parse_status),
  KEY idx_quality_status (quality_status),
  FULLTEXT KEY ftx_document_title (title) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Parsed document asset';

CREATE TABLE IF NOT EXISTS kb_document_chunk (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  chunk_uid VARCHAR(64) NOT NULL UNIQUE,
  document_uid VARCHAR(64) NOT NULL,
  content_uid VARCHAR(64) NOT NULL,
  chunk_index INT NOT NULL,
  chunk_type VARCHAR(64),
  chunk_level VARCHAR(32) COMMENT 'page/section/semantic',
  parent_chunk_uid VARCHAR(64),
  heading_path TEXT,
  page_no INT NULL,
  slide_no INT NULL,
  start_offset INT,
  end_offset INT,
  bbox JSON,
  content MEDIUMTEXT NOT NULL,
  content_hash CHAR(64),
  token_count INT,
  char_count INT,
  evidence_ref VARCHAR(256),
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_document_uid (document_uid),
  KEY idx_content_uid (content_uid),
  KEY idx_chunk_level (chunk_level),
  KEY idx_page_no (page_no),
  KEY idx_slide_no (slide_no),
  FULLTEXT KEY ftx_chunk_content (content) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Document chunk table';

CREATE TABLE IF NOT EXISTS kb_evidence (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  evidence_uid VARCHAR(64) NOT NULL UNIQUE,
  project_uid VARCHAR(64),
  document_uid VARCHAR(64) NOT NULL,
  content_uid VARCHAR(64) NOT NULL,
  chunk_uid VARCHAR(64),
  evidence_type VARCHAR(64),
  source_file_path TEXT,
  source_sha256 CHAR(64),
  source_page_start INT,
  source_page_end INT,
  source_char_start INT,
  source_char_end INT,
  page_no INT NULL,
  slide_no INT NULL,
  heading_path TEXT,
  bbox JSON,
  quote_text MEDIUMTEXT,
  normalized_text MEDIUMTEXT,
  source_location VARCHAR(512),
  confidence DECIMAL(5,2),
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_project_uid (project_uid),
  KEY idx_document_uid (document_uid),
  KEY idx_content_uid (content_uid),
  KEY idx_chunk_uid (chunk_uid),
  FULLTEXT KEY ftx_evidence_text (quote_text, normalized_text) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Fine-grained evidence chain';

CREATE TABLE IF NOT EXISTS kb_document_quality (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  quality_uid VARCHAR(64) NOT NULL UNIQUE,
  document_uid VARCHAR(64) NOT NULL,
  content_uid VARCHAR(64) NOT NULL,
  markdown_length INT,
  heading_count INT,
  table_count INT,
  image_count INT,
  page_count INT,
  empty_page_count INT,
  garbled_ratio DECIMAL(8,4),
  ocr_used TINYINT NOT NULL DEFAULT 0,
  parse_error_count INT NOT NULL DEFAULT 0,
  text_coverage_score DECIMAL(5,2),
  structure_score DECIMAL(5,2),
  table_score DECIMAL(5,2),
  evidence_score DECIMAL(5,2),
  garbled_score DECIMAL(5,2),
  parser_success_score DECIMAL(5,2),
  quality_score DECIMAL(5,2),
  quality_status VARCHAR(64),
  recommended_action VARCHAR(128),
  review_required TINYINT NOT NULL DEFAULT 0,
  review_reason TEXT,
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_document_uid (document_uid),
  KEY idx_content_uid (content_uid),
  KEY idx_quality_status (quality_status),
  KEY idx_quality_score (quality_score),
  KEY idx_recommended_action (recommended_action)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Document parse quality';

CREATE TABLE IF NOT EXISTS kb_project (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_uid VARCHAR(64) NOT NULL UNIQUE,
  project_code VARCHAR(128) NOT NULL UNIQUE,
  project_name VARCHAR(512) NOT NULL,
  client_name VARCHAR(512),
  domain VARCHAR(256),
  project_type VARCHAR(128),
  year_start INT,
  year_end INT,
  description TEXT,
  aliases JSON,
  keywords JSON,
  document_count INT NOT NULL DEFAULT 0,
  core_document_count INT NOT NULL DEFAULT 0,
  completeness_score DECIMAL(5,2),
  has_requirement_doc TINYINT DEFAULT 0,
  has_solution_doc TINYINT DEFAULT 0,
  has_design_doc TINYINT DEFAULT 0,
  has_delivery_doc TINYINT DEFAULT 0,
  has_acceptance_doc TINYINT DEFAULT 0,
  has_training_doc TINYINT DEFAULT 0,
  value_score DECIMAL(5,2),
  status VARCHAR(64) NOT NULL DEFAULT 'ACTIVE',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_project_code (project_code),
  KEY idx_domain (domain),
  FULLTEXT KEY ftx_project_name_desc (project_name, description) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Project master';

CREATE TABLE IF NOT EXISTS kb_project_document (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  project_uid VARCHAR(64) NOT NULL,
  document_uid VARCHAR(64) NOT NULL,
  content_uid VARCHAR(64) NOT NULL,
  candidate_project_code VARCHAR(128),
  candidate_confidence DECIMAL(5,2),
  confirmed_project_code VARCHAR(128),
  confirmed_by VARCHAR(128),
  confirmed_at DATETIME NULL,
  mapping_method VARCHAR(64),
  confidence DECIMAL(5,2),
  is_primary TINYINT NOT NULL DEFAULT 1,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_project_document (project_uid, document_uid),
  KEY idx_project_uid (project_uid),
  KEY idx_document_uid (document_uid),
  KEY idx_content_uid (content_uid),
  KEY idx_confirmed_project_code (confirmed_project_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Project-document mapping';

CREATE TABLE IF NOT EXISTS kb_curated_asset (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  curated_uid VARCHAR(64) NOT NULL UNIQUE,
  project_uid VARCHAR(64),
  asset_type VARCHAR(64) NOT NULL,
  asset_title VARCHAR(1024),
  curated_path TEXT NOT NULL,
  related_content_uids JSON,
  related_document_uids JSON,
  related_evidence_uids JSON,
  generation_method VARCHAR(64),
  generation_status VARCHAR(64),
  version_no INT NOT NULL DEFAULT 1,
  metadata JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  KEY idx_project_uid (project_uid),
  KEY idx_asset_type (asset_type),
  FULLTEXT KEY ftx_curated_asset_title (asset_title) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Curated project knowledge asset';

CREATE TABLE IF NOT EXISTS kb_review_item (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  review_uid VARCHAR(64) NOT NULL UNIQUE,
  target_type VARCHAR(64) NOT NULL,
  target_uid VARCHAR(64) NOT NULL,
  review_status VARCHAR(64) NOT NULL DEFAULT 'PENDING',
  review_reason TEXT,
  reviewer VARCHAR(128),
  review_comment TEXT,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  reviewed_at DATETIME NULL,
  KEY idx_target (target_type, target_uid),
  KEY idx_review_status (review_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Manual review queue';

CREATE TABLE IF NOT EXISTS kb_manual_correction (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  correction_uid VARCHAR(64) NOT NULL UNIQUE,
  target_type VARCHAR(64) NOT NULL,
  target_uid VARCHAR(64) NOT NULL,
  field_name VARCHAR(128) NOT NULL,
  old_value TEXT,
  new_value TEXT,
  correction_reason TEXT,
  corrected_by VARCHAR(128),
  corrected_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_target (target_type, target_uid),
  KEY idx_field_name (field_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Manual correction audit log';

CREATE TABLE IF NOT EXISTS kb_embedding_ref (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  target_type VARCHAR(64) NOT NULL,
  target_uid VARCHAR(64) NOT NULL,
  embedding_model VARCHAR(128),
  vector_store VARCHAR(64),
  vector_collection VARCHAR(128),
  vector_id VARCHAR(128),
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY uk_embedding_target (target_type, target_uid, embedding_model, vector_store),
  KEY idx_vector_collection (vector_collection)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Future vector-store reference';

CREATE TABLE IF NOT EXISTS kb_task_log (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  task_uid VARCHAR(64) NOT NULL,
  task_type VARCHAR(64) NOT NULL,
  target_uid VARCHAR(64),
  log_level VARCHAR(32) NOT NULL,
  message TEXT,
  detail JSON,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY idx_task_uid (task_uid),
  KEY idx_task_type (task_type),
  KEY idx_target_uid (target_uid),
  KEY idx_log_level (log_level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='System task log';

INSERT INTO kb_project (
  project_uid, project_code, project_name, domain, project_type, description, aliases, keywords
) VALUES (
  'proj_default_uncategorized', 'uncategorized', '未归属项目池', '未分类', 'unknown',
  '无法自动归属的历史文档临时进入该项目池。',
  JSON_ARRAY('未归属', '待分类'),
  JSON_ARRAY('待分类', '未知项目')
) ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP;

INSERT INTO kb_schema_version (version, description)
VALUES ('v1.1.0', 'Initial V1.1 schema with file instance/content split, raw vault, curated assets, idempotent parse jobs and evidence refinement')
ON DUPLICATE KEY UPDATE applied_at = applied_at;

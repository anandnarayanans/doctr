import { Component, OnInit, Renderer2 } from '@angular/core';
import { HttpClient, HttpEventType } from '@angular/common/http';
import { interval } from 'rxjs';
import { switchMap, takeWhile, catchError } from 'rxjs/operators';
import { MatTableDataSource } from '@angular/material/table';
import { MatCheckboxModule } from '@angular/material/checkbox';

@Component({
  selector: 'app-file-upload',
  templateUrl: './file-upload.component.html',
  styleUrls: ['./file-upload.component.css'],
})
export class FileUploadComponent implements OnInit {
  file: File | null = null;
  uploadProgress: number = 0;
  translationProgress: number = 0;
  translatedFileUrl: string | null = null;
  translatedPDFUrl: string | null = null;
  translationStatusInterval: any;
  translationId: string | null = null;
  isTranslating: boolean = false;
  showPreview: boolean = false;
  initialFormat: string | null = null; // Ensure initialFormat is either string or null
  renderer: any;
  translatedFiles: any[] = [];
  displayedColumns: string[] = [
    'fileName',
    'project',
    'translationDate',
    'numberOfPages',
    'fileSize',
    'language',
    'downloadLink',
  ];
  dataSource = new MatTableDataSource<any>();

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.fetchTranslations();
  }

  fetchTranslations() {
    this.http
      .get<any[]>('http://localhost:5001/translations')
      .subscribe((translations) => {
        this.translatedFiles = translations.map((translation) => ({
          ...translation,
          download_link: `http://localhost:5001/download/${translation.translation_id}`,
        }));
        this.dataSource.data = this.translatedFiles;
      });
  }

  onFileSelected(event: any) {
    this.file = event.target.files[0];
    console.log('File selected:', this.file);
    if (this.file) {
      this.onUpload();
    }
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    const files = event.dataTransfer?.files;
    if (files?.length) {
      this.file = files[0];
      console.log('File dropped:', this.file);
    }
  }

  onUpload() {
    if (this.file) {
      const formData = new FormData();
      formData.append('file', this.file);

      this.http
        .post<{ message: string; file_path: string; initial_format: string }>(
          'http://localhost:5001/upload',
          formData,
          {
            reportProgress: true,
            observe: 'events',
          }
        )
        .subscribe((event) => {
          if (event.type === HttpEventType.UploadProgress) {
            this.uploadProgress = Math.round(
              (100 * event.loaded) / (event.total || 1)
            );
            console.log('Upload Progress:', this.uploadProgress);
          } else if (event.type === HttpEventType.Response) {
            const filePath = event.body?.file_path ?? null;
            this.initialFormat = event.body?.initial_format ?? null; // Handle undefined case with nullish coalescing
            console.log('File uploaded. File path:', filePath);
            if (filePath) {
              this.startTranslation(filePath);
            }
          }
        });
    }
  }

  startTranslation(filePath: string) {
    this.translationProgress = 0;
    this.translatedFileUrl = null;
    this.translatedPDFUrl = null;
    this.isTranslating = true;
    this.http
      .post<{ message: string; translation_id: string }>(
        'http://localhost:5001/translate',
        { file_path: filePath, initial_format: this.initialFormat }
      )
      .subscribe((response) => {
        this.translationId = response.translation_id;
        console.log('Translation started. Translation ID:', this.translationId);
        this.pollTranslationStatus(this.translationId);
      });
  }

  pollTranslationStatus(translationId: string) {
    this.translationProgress = 0;

    interval(1000)
      .pipe(
        switchMap(() =>
          this.http.get<{ status: string; file_path?: string }>(
            `http://localhost:5001/translation_status/${translationId}`
          )
        ),
        takeWhile(
          (statusResponse) => statusResponse.status !== 'completed',
          true
        ),
        catchError((error) => {
          console.error('Error polling translation status:', error);
          return [];
        })
      )
      .subscribe((statusResponse) => {
        console.log('Translation status response:', statusResponse);
        if (statusResponse.status === 'in_progress') {
          this.translationProgress += 0.5;
          console.log('Translation Progress:', this.translationProgress);
        } else if (statusResponse.status === 'completed') {
          this.translationProgress = 100;
          this.translatedFileUrl = `http://localhost:5001/download/${translationId}`;
          this.translatedPDFUrl = `http://localhost:5001/preview/${translationId}`;
          this.isTranslating = false;
          console.log(
            'Translation completed. Download URL:',
            this.translatedFileUrl
          );
        }
      });
  }

  downloadPDF() {
    if (this.translatedFileUrl && this.initialFormat) {
      const a = document.createElement('a');
      a.href = this.translatedFileUrl;
      a.download = `translated.${this.initialFormat}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    }
  }

  previewPDF() {
    {
      this.showPreview = true;
    }
  }
}

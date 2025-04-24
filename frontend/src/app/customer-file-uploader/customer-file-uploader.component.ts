import { Component, EventEmitter, Input, Output } from '@angular/core';
import { NgxCsvParser } from 'ngx-csv-parser';

@Component({
  selector: 'app-customer-file-uploader',
  templateUrl: './customer-file-uploader.component.html',
  styleUrls: ['./customer-file-uploader.component.css']
})
export class CustomerFileUploaderComponent {
  status: "initial" | "uploading" | "success" | "fail" = "initial"; // Variable to store file status
  file: File | null = null; // Variable to store file
  @Input() headers: string[] = [];
  @Input() label: string = "Upload Data";
  uploaded_headers: string[] = []
  data: {headers: string[], content: string[][]} = {headers: [], content: []};
  error?: string = undefined;
  @Output() newDataEvent = new EventEmitter<{headers: string[], content: string[][]}>();
  @Output() errorEvent = new EventEmitter<string>();

  constructor(private ngxCsvParser: NgxCsvParser){

  }

  ngOnInit(): void {}

  // On file Select
  onChange(event: any) {
    const file: File = event.target.files[0];

    if (file) {
      this.ngxCsvParser.parse(file, {header: false}).pipe().subscribe(
        results => {
          if (Array.isArray(results)){
            this.data.content = results.slice(1);
            this.uploaded_headers = results[0];
            this.data.headers = this.uploaded_headers;
            let expected_headers = new Set<string>(this.headers.map(header => header.toLowerCase()));
            let error_headers: string[] = [];
            this.uploaded_headers.forEach(
              (header) => {if(!expected_headers.has(header)){error_headers.push(header)}}
            );
            if(error_headers.length >0){
              this.error = `Invalid headers: ${error_headers.join(', ')}`;
              this.error += `<br>Expected: ${this.headers.join(', ')}`;
              this.errorEvent.emit(this.error)
            }
            else{
              this.newDataEvent.emit(this.data);
            }
          }
        }
      );
    }
  }
}

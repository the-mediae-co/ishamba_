import { Component } from '@angular/core';
import {EnvironmentService} from "./services/environment.service";

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'iShamba';
  tips_enabled = true
  constructor(private env: EnvironmentService) {
    if (this.env.call_center_data)
      this.tips_enabled = this.env.call_center_data.tips_enabled;
  }
}

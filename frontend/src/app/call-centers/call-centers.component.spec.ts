import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CallCentersComponent } from './call-centers.component';

describe('CallCentersComponent', () => {
  let component: CallCentersComponent;
  let fixture: ComponentFixture<CallCentersComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [CallCentersComponent]
    });
    fixture = TestBed.createComponent(CallCentersComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

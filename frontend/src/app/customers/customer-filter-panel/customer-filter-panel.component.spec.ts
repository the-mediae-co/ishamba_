import { ComponentFixture, TestBed } from '@angular/core/testing';

import { CustomerFilterPanelComponent } from './customer-filter-panel.component';

describe('CustomerFilterPanelComponent', () => {
  let component: CustomerFilterPanelComponent;
  let fixture: ComponentFixture<CustomerFilterPanelComponent>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      declarations: [CustomerFilterPanelComponent]
    });
    fixture = TestBed.createComponent(CustomerFilterPanelComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

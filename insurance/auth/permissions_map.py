PAGE_MAPPING = {
  '/_b_a_c_k_e_n_d/Insurance/get_insurance_companies/': 'SIN-P-GIC',
  '/_b_a_c_k_e_n_d/Insurance/insurance/serve_file/<str:file_id>/': 'SIN-API-SF',
  '/_b_a_c_k_e_n_d/Insurance/insurance/update/.*/': 'SIN-API-FU',
  r'^/_b_a_c_k_e_n_d/Insurance/other_records/?(\?.*)?$': 'SIN-API-OR',
  r'^/_b_a_c_k_e_n_d/Insurance/other_records/report/?(\?.*)?$': 'SIN-API-ORR',
  r'^/_b_a_c_k_e_n_d/Insurance/insurance/?(\?.*)?$': 'SIN-API-IF',
  '/_b_a_c_k_e_n_d/Insurance/get_doctor_list/': 'SIN-P-GDL',
  r'^/_b_a_c_k_e_n_d/Insurance/other_records/refund_approval/': 'SIN-P-RA',
  r'^/_b_a_c_k_e_n_d/Insurance/other_records/overall_approval/': 'SIN-P-OP',
  r'^/_b_a_c_k_e_n_d/Insurance/other_records/final_approval/?(\?.*)?$': 'SIN-P-FA',
  r'^/_b_a_c_k_e_n_d/Insurance/other_records/refund_approval_update/?(\?.*)?$': 'SIN-P-RAU',
  

  'get_insurance_companies/': 'SIN-P-GIC',
  'insurance/serve_file/<str:file_id>/': 'SIN-API-SF',
  'insurance/update/': 'SIN-API-FU',
  'other_records/': 'SIN-API-OR',
  'other_records/report/': 'SIN-P-ORR',
  'get_doctor_list/': 'SIN-P-GDL',
  'other_records/overall_approval/': 'SIN-P-OP',
  'other_records/refund_approval/': 'SIN-P-RA',
  'other_records/final_approval/': 'SIN-P-FA',
  'other_records/refund_approval_update/': 'SIN-P-RAU',
}

PAGE_ACTION_MAPPING = {
    'xxx': {
        'DELETE':'RWD',
    },
}

GEN_ACTION_MAPPING = {
    'POST': 'RW',
    'PUT': 'RW',
    'DELETE': 'RW',
    'GET': 'R',
}
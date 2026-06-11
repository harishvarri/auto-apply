import json
import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_pdf():
    profile_path = 'profile.json'
    pdf_path = 'harish_varri_resume.pdf'
    
    if not os.path.exists(profile_path):
        print(f"Error: {profile_path} not found.")
        return
        
    with open(profile_path, 'r') as f:
        profile = json.load(f)
        
    personal = profile['personal']
    
    # Page setup - 0.5 inch margins for standard professional resume
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    story = []
    
    # Custom styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#1A365D'), # Deep Blue
        alignment=1 # Centered
    )
    
    contact_style = ParagraphStyle(
        'ContactInfo',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#4A5568'), # Slate Gray
        alignment=1 # Centered
    )
    
    heading_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#2B6CB0'), # Royal Blue
        spaceAfter=3
    )
    
    subheading_style = ParagraphStyle(
        'SubHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#2D3748')
    )
    
    meta_style = ParagraphStyle(
        'MetaText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#718096'),
        alignment=2 # Right aligned
    )
    
    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#2D3748'),
        spaceAfter=4
    )
    
    bullet_style = ParagraphStyle(
        'BulletCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#2D3748'),
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    )

    # 1. Header (Name and Contact Details)
    story.append(Paragraph(personal['full_name'], title_style))
    story.append(Spacer(1, 4))
    
    contact_text = f"{personal['location']} | {personal['phone']} | {personal['email']}<br/>"
    contact_text += f"GitHub: {personal['github']} | LinkedIn: {personal['linkedin']}"
    story.append(Paragraph(contact_text, contact_style))
    story.append(Spacer(1, 10))
    
    def add_section_divider(title):
        t = Table([[Paragraph(title, heading_style)]], colWidths=[540])
        t.setStyle(TableStyle([
            ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor('#CBD5E0')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 8),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(t)
        story.append(Spacer(1, 4))

    # 2. Education Section
    add_section_divider("EDUCATION")
    for edu in profile['education']:
        # Left side: Degree, School, Location
        left_text = f"<b>{edu['school']}</b>, {edu['location']}<br/>"
        left_text += f"{edu['degree']} - {edu['major']}"
        if edu.get('gpa'):
            left_text += f" | CGPA/Percentage: {edu['gpa']}"
            
        right_text = f"{edu['start_year']} – {edu['end_year']}"
        
        t_data = [
            [Paragraph(left_text, body_style), Paragraph(right_text, meta_style)]
        ]
        t = Table(t_data, colWidths=[400, 140])
        t.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))
        story.append(t)
    story.append(Spacer(1, 4))

    # 3. Experience Section
    add_section_divider("EXPERIENCE")
    for exp in profile['experience']:
        left_text = f"<b>{exp['company']}</b> – {exp['role']}"
        right_text = f"{exp['start_date']} – {exp['end_date']}"
        
        t_data = [
            [Paragraph(left_text, subheading_style), Paragraph(right_text, meta_style)]
        ]
        t = Table(t_data, colWidths=[400, 140])
        t.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))
        story.append(t)
        
        # Add experience bullet points from description
        desc_bullets = exp['description'].split('. ')
        for bullet in desc_bullets:
            if bullet.strip():
                clean_bullet = bullet.strip().rstrip('.')
                story.append(Paragraph(f"&bull; {clean_bullet}.", bullet_style))
        story.append(Spacer(1, 4))

    # 4. Projects Section
    add_section_divider("PROJECTS")
    for proj in profile['projects']:
        left_text = f"<b>{proj['title']}</b> || <i>{proj['technologies']}</i>"
        
        t_data = [
            [Paragraph(left_text, subheading_style)]
        ]
        t = Table(t_data, colWidths=[540])
        t.setStyle(TableStyle([
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 2),
        ]))
        story.append(t)
        
        desc_bullets = proj['description'].split('. ')
        for bullet in desc_bullets:
            if bullet.strip():
                clean_bullet = bullet.strip().rstrip('.')
                story.append(Paragraph(f"&bull; {clean_bullet}.", bullet_style))
        story.append(Spacer(1, 4))

    # 5. Technical Skills
    add_section_divider("TECHNICAL SKILLS")
    skills = profile['skills']
    skills_lines = [
        f"<b>Programming Languages:</b> {', '.join(skills['programming_languages'])}",
        f"<b>Data & Analytics:</b> {', '.join(skills['data_analytics'])}",
        f"<b>Frameworks & Technologies:</b> {', '.join(skills['frameworks'])}",
        f"<b>Core Subjects:</b> {', '.join(skills['core_subjects'])}",
        f"<b>Soft Skills:</b> {', '.join(skills['soft_skills'])}"
    ]
    for line in skills_lines:
        story.append(Paragraph(line, body_style))
    story.append(Spacer(1, 4))

    # 6. Certifications
    add_section_divider("CERTIFICATIONS")
    for cert in profile['certifications']:
        story.append(Paragraph(f"&bull; {cert}", bullet_style))
    story.append(Spacer(1, 4))

    # 7. Achievements
    add_section_divider("ACHIEVEMENTS")
    achievements = [
        "<b>Hackathons:</b> Hackeverse (Vista 2K24) – First Place, Washington Hackathon – Top 5, KL University Code4Change 2025 – Team Lead, ANITS AI-ML Hackathon – Finalist.",
        "<b>Workshops:</b> Conducted a technical workshop for NCPL non-IT employees at Hrud.ai, providing technical guidance, resolving issues, and assisting development teams."
    ]
    for ach in achievements:
        story.append(Paragraph(f"&bull; {ach}", bullet_style))
        
    doc.build(story)
    print(f"Successfully generated {pdf_path}")

if __name__ == '__main__':
    generate_pdf()

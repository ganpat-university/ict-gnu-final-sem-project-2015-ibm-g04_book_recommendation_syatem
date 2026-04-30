const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, LevelFormat, BorderStyle, WidthType,
  ShadingType, PageNumber, PageBreak, Footer, TabStopType, TabStopPosition
} = require('docx');
const fs = require('fs');

const border = { style: BorderStyle.SINGLE, size: 1, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };
const headerBorder = { style: BorderStyle.SINGLE, size: 1, color: "2B579A" };
const headerBorders = { top: headerBorder, bottom: headerBorder, left: headerBorder, right: headerBorder };

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
}
function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
}
function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] });
}
function h4(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_4, children: [new TextRun({text, bold: true, size: 22, color: "404040" })] });
}
function para(text, opts = {}) {
  let runs = [new TextRun({ text, font: "Arial", size: 22, italics: opts.italic, bold: opts.bold, color: opts.color })];
  return new Paragraph({
    alignment: opts.center ? AlignmentType.CENTER : AlignmentType.JUSTIFIED,
    spacing: { after: 160, line: 276 },
    children: runs
  });
}
function caption(text) {
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 160 },
    children: [new TextRun({ text, font: "Arial", size: 20, italics: true })]
  });
}
function bullet(text) {
  return new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    spacing: { after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 22 })]
  });
}
function numbered(text) {
  return new Paragraph({
    numbering: { reference: "numbers", level: 0 },
    spacing: { after: 80 },
    children: [new TextRun({ text, font: "Arial", size: 22 })]
  });
}
function space(n = 1) {
  return new Paragraph({ children: [new TextRun("")], spacing: { after: n * 80 } });
}
function codeSnippetPlaceholder() {
  return [
    para("[CODE SNIPPET PLACEHOLDER: Please replace the code block below with a direct screenshot from your IDE (e.g., RStudio or VS Code) showing line numbers and native syntax highlighting.]", { bold: true, color: "B22222" }),
    new Paragraph({
      spacing: { after: 200 },
      shading: { fill: "F3F3F3", type: ShadingType.CLEAR },
      children: [new TextRun({ text: "// IDE Code Screenshot goes here...", font: "Courier New", size: 20, color: "2B2B2B" })]
    })
  ];
}

function makeHeaderRow(cols, widths) {
  return new TableRow({
    children: cols.map((text, i) => new TableCell({
      borders: headerBorders,
      width: { size: widths[i], type: WidthType.DXA },
      shading: { fill: "1F3864", type: ShadingType.CLEAR },
      margins: { top: 100, bottom: 100, left: 150, right: 150 },
      children: [new Paragraph({ children: [new TextRun({ text, font: "Arial", size: 22, bold: true, color: "FFFFFF" })] })]
    }))
  });
}

function makeDataRow(cols, widths, rowIdx) {
  return new TableRow({
    children: cols.map((text, j) => new TableCell({
      borders,
      width: { size: widths[j], type: WidthType.DXA },
      shading: { fill: rowIdx % 2 === 0 ? "F5F8FF" : "FFFFFF", type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 150, right: 150 },
      children: [new Paragraph({ children: [new TextRun({ text, font: "Arial", size: 20 })] })]
    }))
  });
}

const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }]
      },
      {
        reference: "numbers",
        levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }]
      },
    ]
  },
  styles: {
    default: { document: { run: { font: "Arial", size: 22 } } },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: "1F3864" },
        paragraph: { spacing: { before: 360, after: 200 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F3864", space: 1 } } }
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: "2B579A" },
        paragraph: { spacing: { before: 280, after: 160 }, outlineLevel: 1 }
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: "404040" },
        paragraph: { spacing: { before: 200, after: 120 }, outlineLevel: 2 }
      },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1260, bottom: 1440, left: 1260 }
      }
    },
    footers: {
      default: new Footer({
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({ text: "IBM Project Report — NovelNest Recommendation System   |   Page ", font: "Arial", size: 18, color: "888888" }),
              new TextRun({ children: [PageNumber.CURRENT], font: "Arial", size: 18, color: "888888" }),
            ]
          })
        ]
      })
    },
    children: [

      // TITLE PAGE
      new Paragraph({ spacing: { before: 800, after: 0 }, children: [new TextRun("")] }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 60 },
        children: [new TextRun({ text: "IBM PROJECT REPORT", font: "Arial", size: 52, bold: true, color: "1F3864" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 200 },
        children: [new TextRun({ text: "On", font: "Arial", size: 28, color: "555555" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 120 },
        children: [new TextRun({ text: "NovelNest: A Personalized Book Recommendation System", font: "Arial", size: 38, bold: true, color: "2B579A" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 300 },
        children: [new TextRun({ text: "using Hybrid Analytics and AWS EC2", font: "Arial", size: 30, bold: false, color: "2B579A" })]
      }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [4680, 4680],
        rows: [
          new TableRow({
            children: [
              new TableCell({
                borders: headerBorders, width: { size: 4680, type: WidthType.DXA },
                shading: { fill: "E8F0FE", type: ShadingType.CLEAR },
                margins: { top: 160, bottom: 160, left: 200, right: 200 },
                children: [
                  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: "Developed By", font: "Arial", size: 24, bold: true, color: "1F3864" })] }),
                  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: "Kathan Desai (24162173001)", font: "Arial", size: 21 })] }),
                  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: "Shubhashish Das (22162171028)", font: "Arial", size: 21 })] }),
                  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: "Nachiket Patel (22162171019)", font: "Arial", size: 21 })] }),
                ]
              }),
              new TableCell({
                borders: headerBorders, width: { size: 4680, type: WidthType.DXA },
                shading: { fill: "FFF8E8", type: ShadingType.CLEAR },
                margins: { top: 160, bottom: 160, left: 200, right: 200 },
                children: [
                  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 }, children: [new TextRun({ text: "Guided By", font: "Arial", size: 24, bold: true, color: "1F3864" })] }),
                  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: "Prof. Umesh Lakhtariya (Internal)", font: "Arial", size: 21 })] }),
                  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 40 }, children: [new TextRun({ text: "Mr. Anoj Dixit (External)", font: "Arial", size: 21 })] }),
                ]
              }),
            ]
          })
        ]
      }),

      space(3),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "Submitted to", font: "Arial", size: 24, bold: true })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "Faculty of Engineering and Technology", font: "Arial", size: 22 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "Institute of Computer Technology", font: "Arial", size: 22 })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "Ganpat University, Mehsana, Gujarat", font: "Arial", size: 22 })] }),
      space(2),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "Academic Year — 2025–2026", font: "Arial", size: 28, bold: true, color: "1F3864" })] }),
      new Paragraph({ children: [new PageBreak()] }),

      // CERTIFICATE PAGE
      new Paragraph({ spacing: { before: 400, after: 0 }, children: [new TextRun("")] }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 80 },
        children: [new TextRun({ text: "CERTIFICATE", font: "Arial", size: 40, bold: true, color: "1F3864" })]
      }),
      new Paragraph({
        alignment: AlignmentType.CENTER, spacing: { after: 40 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "1F3864", space: 1 } },
        children: [new TextRun({ text: " ", font: "Arial", size: 8 })]
      }),
      space(2),
      para("This is to certify that the project entitled \"NovelNest: A Personalized Book Recommendation System using Hybrid Analytics and AWS EC2\" has been successfully completed by the following students of the Bachelor of Engineering program at the Institute of Computer Technology, Ganpat University, Mehsana, Gujarat, India, during the academic year 2025–2026."),
      space(),
      para("The project has been carried out under the supervision and guidance of Prof. Umesh Lakhtariya (Internal Guide) and Mr. Anoj Dixit (External Guide). The work described in this report is original, credible, and meets the requirements specified by the university for the partial fulfillment of the degree."),
      space(2),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3120, 3120, 3120],
        rows: [
          new TableRow({
            children: [
              new TableCell({ borders: headerBorders, width: { size: 3120, type: WidthType.DXA }, shading: { fill: "1F3864", type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 150, right: 150 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Enrollment No.", font: "Arial", size: 22, bold: true, color: "FFFFFF" })] })] }),
              new TableCell({ borders: headerBorders, width: { size: 3120, type: WidthType.DXA }, shading: { fill: "1F3864", type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 150, right: 150 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Student Name", font: "Arial", size: 22, bold: true, color: "FFFFFF" })] })] }),
              new TableCell({ borders: headerBorders, width: { size: 3120, type: WidthType.DXA }, shading: { fill: "1F3864", type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 150, right: 150 }, children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Signature", font: "Arial", size: 22, bold: true, color: "FFFFFF" })] })] }),
            ]
          }),
          ...[
            ["24162173001", "Kathan Desai", ""],
            ["22162171028", "Shubhashish Das", ""],
            ["22162171019", "Nachiket Patel", ""],
          ].map((row, i) => new TableRow({
            children: row.map((cell, j) => new TableCell({
              borders,
              width: { size: 3120, type: WidthType.DXA },
              shading: { fill: i % 2 === 0 ? "F5F8FF" : "FFFFFF", type: ShadingType.CLEAR },
              margins: { top: 100, bottom: 100, left: 150, right: 150 },
              children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: cell, font: "Arial", size: 20 })] })]
            }))
          }))
        ]
      }),
      space(3),
      new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: "Internal Guide: Prof. Umesh Lakhtariya", font: "Arial", size: 22, bold: true })] }),
      new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: "Signature: _______________________________", font: "Arial", size: 22 })] }),
      space(),
      new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: "External Guide: Mr. Anoj Dixit", font: "Arial", size: 22, bold: true })] }),
      new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: "Signature: _______________________________", font: "Arial", size: 22 })] }),
      space(),
      new Paragraph({ spacing: { after: 80 }, children: [new TextRun({ text: "Head of Department: _______________________________", font: "Arial", size: 22, bold: true })] }),
      new Paragraph({ children: [new PageBreak()] }),

      // ACKNOWLEDGEMENT
      h1("ACKNOWLEDGEMENT"),
      para("The successful completion of this project would not have been possible without the generous support, guidance, and encouragement of numerous individuals. We take this opportunity to express our heartfelt gratitude to all those who contributed — directly or indirectly — to the realization of this work."),
      para("We are deeply grateful to Prof. Umesh Lakhtariya, our Internal Project Guide at the Institute of Computer Technology, Ganpat University, for his unwavering support, insightful feedback, and patient mentorship throughout the entirety of this project. His technical expertise and constructive critique shaped our approach at every stage, from requirement analysis to final deployment."),
      para("We would also like to extend our sincere thanks to Mr. Anoj Dixit, our External Guide, whose industry perspective and practical experience proved invaluable in bridging the gap between academic theory and real-world implementation. His guidance regarding structural architecture significantly elevated the quality of this work."),
      para("Our gratitude also goes to the Faculty of Engineering and Technology at Ganpat University for providing us with the academic environment, computing resources, and laboratory access required to carry out this project effectively."),
      para("We acknowledge the open-source community — particularly the contributors to Flask, Pandas, and Scikit-learn — whose freely available tools and comprehensive documentation made it possible to build a sophisticated, production-grade system within an academic timeline."),
      para("Finally, we thank our families and peers for their endless encouragement and understanding. This project, like all meaningful work, was a team effort in the truest sense."),
      space(2),
      new Paragraph({
        alignment: AlignmentType.RIGHT, spacing: { after: 60 },
        children: [new TextRun({ text: "Kathan Desai", font: "Arial", size: 22, bold: true })]
      }),
      new Paragraph({
        alignment: AlignmentType.RIGHT, spacing: { after: 60 },
        children: [new TextRun({ text: "Shubhashish Das", font: "Arial", size: 22, bold: true })]
      }),
      new Paragraph({
        alignment: AlignmentType.RIGHT, spacing: { after: 60 },
        children: [new TextRun({ text: "Nachiket Patel", font: "Arial", size: 22, bold: true })]
      }),
      new Paragraph({ children: [new PageBreak()] }),

      // ABSTRACT
      h1("ABSTRACT"),
      para("The NovelNest system is a web-based application built with the primary objective of providing users with accurate, contextually relevant book suggestions. To achieve this, we have integrated multiple complementary recommendation techniques within a unified hybrid framework: popularity-based filtering, content-based filtering, and collaborative filtering. By synthesizing these approaches, we have engineered a system that is robust, scalable, and highly adaptable to diverse user preferences."),
      para("We have harnessed the comprehensive Goodbooks-10k dataset, standardizing thousands of book metadata entries and millions of user interactions. Throughout the development lifecycle, we iteratively processed this raw data, enabling our recommendation models precisely surface accurate outputs from historically latent user-preference patterns."),
      para("Furthermore, we have transitioned NovelNest toward a robust architectural backend using Flask, abandoning heavier prototyping toolsets to enhance response times and minimize resource overhead. The application also securely mandates Google OAuth and custom OTP-driven email verification mechanisms, guaranteeing highly controlled platform entry prior to data presentation."),
      para("Our system was developed and structured over a four-month deployment timeline, ultimately resulting in a productionized framework actively hosted via Amazon Web Services (AWS EC2). Ultimately, this project serves as a sophisticated, comprehensive solution answering modern challenges of information overload in literary discovery."),
      new Paragraph({ children: [new PageBreak()] }),

      // TABLE OF CONTENTS
      h1("INDEX"),
      ...[
        ["Certificate", "2"],
        ["Acknowledgement", "3"],
        ["Abstract", "4"],
        ["CHAPTER 1: INTRODUCTION", "6"],
        ["  1.1 Key Features of the System", "7"],
        ["  1.2 Technologies Integrated", "7"],
        ["CHAPTER 2: PROJECT SCOPE", "8"],
        ["  2.1 Scope of the Project", "8"],
        ["  2.2 Current Scope", "8"],
        ["  2.3 Out of Scope", "8"],
        ["  2.4 Extended Scope — Future Directions", "9"],
        ["CHAPTER 3: SOFTWARE AND HARDWARE REQUIREMENTS", "10"],
        ["  3.1 Hardware Requirements", "10"],
        ["  3.2 Software Requirements", "10"],
        ["  3.3 Python Libraries Used", "11"],
        ["  3.4 Cloud Services Configuration", "11"],
        ["CHAPTER 4: PROCESS MODEL", "12"],
        ["  4.1 Development Phases", "12"],
        ["CHAPTER 5: PROJECT PLAN", "13"],
        ["  5.1 List of Major Activities", "13"],
        ["  5.2 Estimated Time Duration", "15"],
        ["CHAPTER 6: IMPLEMENTATION DETAILS", "16"],
        ["  6.1 Architecture Overview", "16"],
        ["  6.2 Data Collection and Preprocessing", "16"],
        ["  6.3 The Survey-Driven Strategy", "17"],
        ["  6.4 Hybrid Recommendation Assembly", "18"],
        ["  6.5 Backend API Implementation", "19"],
        ["CHAPTER 7: AWS EC2 DEPLOYMENT", "20"],
        ["  7.1 EC2 Instance Setup", "20"],
        ["  7.2 Deployment Processes", "20"],
        ["CHAPTER 8: TESTING AND QUALITY ASSURANCE", "21"],
        ["  8.1 Testing Strategy", "21"],
        ["  8.2 Unit Testing", "21"],
        ["  8.3 Validated Outcomes", "22"],
        ["CHAPTER 9: CONCLUSION AND FUTURE WORK", "23"],
        ["  9.1 Conclusion", "23"],
        ["  9.2 Future Work", "23"],
        ["CHAPTER 10: REFERENCES", "24"],
      ].map(([title, page]) =>
        new Paragraph({
          tabStops: [{ type: TabStopType.RIGHT, position: 9000, leader: TabStopPosition.NONE }],
          spacing: { after: 60 },
          children: [
            new TextRun({ text: title, font: "Arial", size: 21, bold: title.startsWith("CHAPTER") }),
            new TextRun({ text: "\t" + page, font: "Arial", size: 21 }),
          ]
        })
      ),
      new Paragraph({ children: [new PageBreak()] }),

      // CHAPTER 1
      h1("CHAPTER 1: INTRODUCTION"),
      para("The exponential increase in the availability of digital content has fundamentally transformed the way users access, consume, and interact with information. In the domain of literature and book discovery specifically, the proliferation of online platforms has made millions of book titles accessible to readers at any given moment. While this abundance is a privilege, it introduces a paradox: too much choice can be paralyzing."),
      para("This challenge is commonly referred to as information overload. To mitigate this phenomenon, we have developed NovelNest, a scalable, survey-driven book recommendation engine. By analyzing personalized inputs derived from user genre selections and read history, our system cross-references preferences against millions of historical data points, distilling recommendations distinctly curated for the individual."),
      para("In this phase, we have implemented sophisticated filtering logics housed within a streamlined web interface. We departed from traditional static filtering mechanisms and opted for dynamic, context-aware mathematical modeling structures."),
      space(),
      h2("1.1 Key Features of the System"),
      bullet("Collaborative Filtering leveraging cosine similarity metrics across sparse matrices for precise peer-based evaluation."),
      bullet("A unique 'Survey-First' initialization architecture, mitigating the notorious cold-start problem faced by new recommendation engines."),
      bullet("Dual-layer Authentication integrating Flask-Dance (Google OAuth) and customized Email OTP verification tools via Flask-Mail."),
      bullet("Full-stack delivery utilizing a Flask-based RESTful backend integrated natively with Jinja2 front-end templates without relying on heavy rapid-prototyping frontends."),
      bullet("Lightweight local JSON-based persistent storage for streamlined session persistence mapping and user interaction data."),
      space(),
      h2("1.2 Technologies Integrated"),
      bullet("Machine Learning & Computation: Python 3.10+, Scikit-learn, Scipy, Numpy, Pandas."),
      bullet("Backend Framework & Serving: Flask, Gunicorn."),
      bullet("Authentication: OAuth2.0, Flask-Mail (SMTP integration)."),
      bullet("Cloud Computing: Amazon Web Services (AWS) EC2 for high-availability production application hosting."),
      bullet("Version Control: Git combined with SSH scripting automation for continuous delivery."),
      new Paragraph({ children: [new PageBreak()] }),

      // CHAPTER 2
      h1("CHAPTER 2: PROJECT SCOPE"),
      h2("2.1 Scope of the Project"),
      para("We have explicitly bounded the scope of this NovelNest initiative to fit within a stringent four-month timeline while retaining robust delivery requirements. The primary objective is to finalize an end-to-end framework capable of processing real user-input seamlessly into a polished dashboard."),
      space(),
      h2("2.2 Current Scope"),
      para("In this iteration, we have successfully realized the following system components:"),
      numbered("Engineered the Flask API wrapper accommodating local data ingestion alongside custom routing scripts."),
      numbered("Refined a robust authentication gate capturing precise user identities dynamically."),
      numbered("Computed complex mathematical clustering models defining our Hybrid filtering algorithms pipeline."),
      numbered("Designed frontend template logic delivering intuitive user-survey experiences."),
      numbered("Migrated the resulting codebase into an AWS EC2 compute instance for external network access."),
      space(),
      h2("2.3 Out of Scope"),
      para("Due to infrastructure scaling boundaries during our four-month cycle, we have actively deprioritized the following implementations:"),
      bullet("External object decoupling using AWS S3 storage arrays (opting instead for unified local EC2 disk configurations)."),
      bullet("Real-time distributed streaming analytics via big data event processors."),
      bullet("Heavy client-side rendering utilizing React or Angular bindings for single page application delivery."),
      space(),
      h2("2.4 Extended Scope — Future Directions"),
      para("By building this framework efficiently, we laid groundwork intended to support subsequent expansions easily, including the integration of specialized NLP structures parsing user reviews, or adopting automated serverless functional architectures (such as AWS Lambda)."),
      new Paragraph({ children: [new PageBreak()] }),

      // CHAPTER 3
      h1("CHAPTER 3: SOFTWARE AND HARDWARE REQUIREMENTS"),
      para("To ensure continuous functionality and deterministic deployments, we have stringently documented the required infrastructure needed to compile, launch, and interpret the NovelNest system. These resources guided subsequent cloud allocations during our migration testing phase."),
      space(),
      h2("3.1 Hardware Requirements"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3120, 6240],
        rows: [
          makeHeaderRow(["Component", "Requirement"], [3120, 6240]),
          ...([
            ["Processor", "2.5 GHz multi-core architecture"],
            ["Memory (RAM)", "8 GB minimal (Required due to Pandas in-memory dataframe sizes)"],
            ["Storage", "25 GB threshold allocation (Supporting local dataset placement)"],
            ["Network", "Consistent broadband (Required for external OAuth callbacks and API verifications)"],
          ]).map((row, i) => makeDataRow(row, [3120, 6240], i))
        ]
      }),
      space(2),
      h2("3.2 Software Requirements"),
      bullet("Operating System Environment: Unix/Linux environments natively prioritized (Ubuntu 22.04 configured for production deployment)."),
      bullet("Programming Interpreter: Python 3.10."),
      bullet("Hosting Toolkits: Secure Shell (SSH) clients, bash environment compatibility."),
      space(),
      h2("3.3 Python Libraries Used"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2340, 7020],
        rows: [
          makeHeaderRow(["Library", "Core Application Task"], [2340, 7020]),
          ...([
            ["pandas", "Efficient tabular reading mapping metadata records quickly."],
            ["scikit-learn", "Core cosine mapping protocols driving content-based discovery."],
            ["scipy", "Compressed Sparse Row generation lowering intensive calculation limitations."],
            ["Flask", "Primary WSGI network routing engine orchestrating internal API mappings."],
            ["Flask-Dance", "Google OAuth handler establishing remote protocol synchronizations."],
            ["Flask-Mail", "Simple Mail Transfer Protocol client invoking the OTP dispatches."],
          ]).map((row, i) => makeDataRow(row, [2340, 7020], i))
        ]
      }),
      space(2),
      h2("3.4 Cloud Services Configuration"),
      para("We have exclusively mandated Amazon Elastic Compute Cloud (EC2) as our central production infrastructure vector. The instance (provisioned via an Ubuntu template model) runs the Gunicorn production server dynamically bound to the primary web interfaces and the public host at 13.204.232.136:5000 for universal access."),
      new Paragraph({ children: [new PageBreak()] }),

      // CHAPTER 4
      h1("CHAPTER 4: PROCESS MODEL"),
      para("Throughout our four-month project spectrum, we dynamically incorporated an Incremental and Modular Development architecture. We avoided attempting monolithic releases; instead, we sequentially implemented, isolated, and tested each component logic prior to total composition."),
      space(),
      h2("4.1 Development Phases"),
      h3("4.1.1 Preprocessing and Foundation Phase"),
      para("We initialized analytical extraction against the raw Goodbooks datasets, generating sparse matrices compatible with recommendation libraries."),
      h3("4.1.2 Recommender Architecture Phase"),
      para("In this sub-phase, we implemented the popularity, content-based, and collaborative filtering engines linearly, culminating in the cohesive `HybridRecommender` composite wrapper."),
      h3("4.1.3 Interface Refinement Phase"),
      para("We finalized the transformation from basic exploratory prototyping tools to the Flask and Jinja2 templating system, unlocking custom styling and responsive interface metrics."),
      h3("4.1.4 Cloud Delivery Phase"),
      para("This final activity encapsulated local code extraction into the cloud instance, wiring public IPs and configuring process-managers using integrated bash scripts."),
      new Paragraph({ children: [new PageBreak()] }),

      // CHAPTER 5
      h1("CHAPTER 5: PROJECT PLAN"),
      para("To adhere to our definitive four-month academic criteria limitation, we organized the core execution across comprehensive chronological timelines. The timeline effectively distributed workload capacities across logic formulation and integration tests."),
      space(),
      h2("5.1 List of Major Activities"),
      h3("5.1.1 Requirement Study and Blueprint Generation"),
      para("We surveyed existing methodologies against cold start phenomena and settled aggressively on the 'Survey Input Proxy' solution."),
      h3("5.1.2 Data Parsing and Dimensionality Reduction"),
      para("We compressed 6-million rating interactions by discarding inherently sparse peripheral user-data, reinforcing core density levels."),
      h3("5.1.3 Interface Construction and Access Limitations"),
      para("Authentication structures were tightly bound, preventing unauthorized resource execution without verified credential keys."),
      space(),
      h2("5.2 Estimated Time Duration"),
      para("The cumulative development lifecycle encompassed virtually 16 weeks (4 months). Time blocks denote parallel execution alignments."),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [6240, 3120],
        rows: [
          makeHeaderRow(["Activity Designation", "Allocated Work Weeks"], [6240, 3120]),
          ...([
            ["Phase Mapping & Requirement Analysis", "2 Weeks"],
            ["Exploratory Data Evaluation", "2 Weeks"],
            ["Algorithmic Logic Formulation & Tuning", "4 Weeks"],
            ["Flask Routing & HTML Interface Assembly", "3 Weeks"],
            ["Auth Implementations (OTP + Google OAuth)", "2 Weeks"],
            ["AWS EC2 Transfer and Configurations", "1.5 Weeks"],
            ["End-to-End Integrity Review and Documentation", "1.5 Weeks"],
          ]).map((row, i) => makeDataRow(row, [6240, 3120], i))
        ]
      }),
      new Paragraph({ children: [new PageBreak()] }),

      // CHAPTER 6
      h1("CHAPTER 6: IMPLEMENTATION DETAILS"),
      h2("6.1 Architecture Overview"),
      para("We have deployed the NovelNest system as a robust RESTful Flask server. Centralized requests evaluate active user session parameters and intelligently route subsequent payload dispatches to either the `verify_signup` gate or the primary analytical `index` recommendation arrays."),
      space(),
      h2("6.2 Data Collection and Preprocessing"),
      para("By applying Python dataframes, we standardized unstructured raw data formats. Data labels were stripped of anomalies, missing metrics were forcefully dropped, and text components were completely normalized prior to evaluation modeling."),
      para("[PLACEHOLDER - BAR CHART: Please replace this text with a Bar Chart. The chart must use a flat 'Steel Blue' color for all bars, with data labels clearly placed on top of each bar.]", { center: true, bold: true, color: "0000FF" }),
      caption("Figure 6.1: Distribution of Filtered Ratings Across Primary Genres"),
      space(),
      h2("6.3 The Survey-Driven Strategy"),
      para("To circumvent new-user zero-history limitations, our implementation introduces a dynamic survey forcing initialization values. By matching the surveyed genre tags and existing reads to an equivalent 'proxy user' hidden within the established data sets, we simulate historical depth instantly."),
      space(),
      h2("6.4 Hybrid Recommendation Assembly"),
      h3("6.4.1 Collaborative Matrix Interpolation"),
      para("We have implemented complex vector similarity equations via Scikit-learn architectures matching proximity metrics effectively."),
      para("[PLACEHOLDER - SCATTER PLOT: Please replace this text with a Scatter Plot. Specify that 'Actual' user preference data points should be represented as Red dots, and 'Predicted' clustering data points should be Blue dots or diamonds.]", { center: true, bold: true, color: "0000FF" }),
      caption("Figure 6.2: Matrix Proximity Distance Mapping (Actual vs Predicted User Scores)"),
      space(),
      h3("6.4.2 Content-Based Overlays"),
      para("Our system also filters book metadata sequentially, matching textual correlations. This process reinforces structural integrity preventing misaligned categorizations during query expansion techniques."),
      space(),
      h2("6.5 Backend API Implementation"),
      para("We generated precise routing topologies. The snippet below highlights the strict validation checks we process ensuring unauthorized interactions are explicitly blocked by the Flask environment configuration."),
      ...codeSnippetPlaceholder(),
      new Paragraph({ children: [new PageBreak()] }),

      // CHAPTER 7
      h1("CHAPTER 7: AWS EC2 DEPLOYMENT"),
      h2("7.1 EC2 Instance Setup"),
      para("We have transitioned the local development repository directly to an Amazon Elastic Compute Cloud instance. Utilizing Linux configurations, we executed environmental cloning via Git integrations."),
      space(),
      h2("7.2 Deployment Processes"),
      para("Within the deployment lifecycle, we composed dedicated bash shells (`run.sh` and `stop.sh`) governing Gunicorn operations seamlessly. These shell operations manage active threading structures across configured HTTP web ports concurrently (specifically bound linearly to port 5000)."),
      space(),
      h2("7.3 Deployment Challenges and Solutions"),
      para("Early memory constraint failures ('Killed' signals) caused by handling mass dataframes inside lower-tier instances prompted us to dynamically inject load cap limits, reducing memory utilization overhead heavily without compromising analytical integrity."),
      new Paragraph({ children: [new PageBreak()] }),

      // CHAPTER 8
      h1("CHAPTER 8: TESTING AND QUALITY ASSURANCE"),
      h2("8.1 Testing Strategy"),
      para("We systematically benchmarked components internally to guarantee consistent behavior across edge cases. Unit implementations isolated code fragments effectively."),
      space(),
      h2("8.2 Validated Outcomes"),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [4680, 2340, 2340],
        rows: [
          makeHeaderRow(["Testing Function", "Validation Standard", "Current Status"], [4680, 2340, 2340]),
          ...([
            ["OAuth Callback Redirection", "Secure Parsing Delivery", "Passed"],
            ["Proxy User Similarity Searching", "Accurate Sub-second Return", "Passed"],
            ["Flask Multi-threading Resolution", "Parallel Processing Capability", "Passed"],
            ["OTP Email Expiration Mapping", "Time Block Eradication", "Passed"],
          ]).map((row, i) => makeDataRow(row, [4680, 2340, 2340], i))
        ]
      }),
      new Paragraph({ children: [new PageBreak()] }),

      // CHAPTER 9
      h1("CHAPTER 9: CONCLUSION AND FUTURE WORK"),
      h2("9.1 Conclusion"),
      para("We have robustly fulfilled our core objective, orchestrating NovelNest into a dynamic, web-accessible system solving literary information overload dynamically via machine intelligence frameworks. Over our comprehensive four-month development iteration schedule, we systematically abandoned limiting prototype solutions optimizing deeply aligned backends using Flask integration elements exclusively built for production cloud execution via AWS EC2 configurations."),
      space(),
      h2("9.2 Future Work"),
      para("The foundational stability of NovelNest actively supports wide integrations advancing system intelligence natively in subsequent phases."),
      h3("9.2.1 Real-Time Streaming"),
      para("Introducing event-streaming components observing minute interactive variances (e.g. dwell time on specific UI book blocks) updating predictive matrices actively."),
      h3("9.2.2 Distributed Cloud Augmentation"),
      para("While we actively host the server within an EC2 silo, deploying AWS S3 static data references internally expands processing thresholds dramatically extending capability margins universally."),
      new Paragraph({ children: [new PageBreak()] }),

      // CHAPTER 10
      h1("CHAPTER 10: REFERENCES"),
      numbered("Scikit-learn Developers. (2025). Scikit-learn Documentation: Machine Learning Configurations. Retrieved from https://scikit-learn.org"),
      numbered("Flask Foundation. (2025). Flask Framework Operations. Retrieved from https://flask.palletsprojects.com/"),
      numbered("Pandas Development Team. (2025). High-performance Data Manipulation. Retrieved from https://pandas.pydata.org/"),
      numbered("Amazon Web Services Documentation. (2025). EC2 Infrastructure Hosting. Retrieved from https://docs.aws.amazon.com/ec2/"),
      numbered("Koren, Y., Bell, R. (2009). Matrix Factorization Techniques for Recommender Systems. IEEE."),
    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('IBM_Project_Report_NovelNest.docx', buffer);
  console.log('SUCCESS: Document written to IBM_Project_Report_NovelNest.docx');
}).catch(err => {
  console.error('ERROR:', err);
  process.exit(1);
});

# Passport Photo Tool - Requirements Document

## Project Overview
Build a web-based tool that converts user photos into passport-sized photos, formatted for printing. The tool runs entirely in the browser with no backend required.

## Core Functionality

### 1. Photo Upload
- Accept image uploads via file input (JPEG, PNG)
- Support drag-and-drop upload
- Load image directly into browser (no server upload)

### 2. Image Cropping
- Display uploaded image in an interactive cropper
- Allow user to select and adjust crop area
- Maintain aspect ratio appropriate for passport photos (typically 1:1 square)
- Show guidelines/overlay to help user position face correctly

### 3. Passport Photo Standards
- Final photo dimensions: 2x2 inches at 300 DPI (600x600 pixels)
- Head should occupy 50-70% of the frame height
- Show visual guides (ghostly silhouette overlay) for proper head positioning
- Plain background (user provides, or use built-in AI background whitener)

### 4. Print Layout Generation
- Create a 4x6 inch print sheet at 300 DPI (1200x1800 pixels)
- Tile 2 passport photos (1x2 grid) centered on the sheet
- This provides a 1-inch "safe zone" margin on all sides to prevent printer clipping
- Add light cut lines around photos
- Maintain high quality throughout resize process

### 5. Download
- Generate final image file (JPEG or PNG)
- Trigger automatic download to user's computer
- Filename should be descriptive (e.g., "passport-photos-print-sheet.jpg")

## Technical Requirements

### Frontend Stack
- HTML5 for structure
- CSS3 for styling
- Vanilla JavaScript or minimal framework
- Canvas API for image manipulation
- FileReader API for local file handling

### Recommended Libraries
- **Cropper.js** - interactive image cropping with good UX
- Alternatively, build custom cropper with Canvas API (more control, more code)

### Browser Compatibility
- Modern browsers (Chrome, Firefox, Safari, Edge)
- Mobile responsive design optional but recommended

### Performance
- Handle images up to 10MB without issues
- Processing should feel instant (<1 second for crop and layout)

## User Interface

### Layout
1. Upload area (large, prominent)
2. Cropping interface (appears after upload)
3. Preview of final print sheet
4. Download button

### Instructions
- Clear, brief instructions at each step
- Visual guides showing correct head positioning
- Optional: Example of correct vs incorrect photos

### Visual Design
- Clean, minimal interface
- High contrast for usability
- Professional appearance (this is for official documents)

## Optional Enhancements

## Included Features
- Background removal/whitening using MediaPipe AI
- Interactive cropping with positioning guides
- 4x6" print sheet generation with 2x2" photo tiling
- High-quality JPEG download

## Optional Enhancements (Removed for MVP)
- Multiple photo sizes in one tool (passport, visa, ID card)
- Print at home vs professional print optimization
- Save crop settings for retakes
- Batch processing multiple photos

## Implementation Steps

1. **Set up project structure**
   - Create HTML file with basic layout
   - Add CSS for styling
   - Include JavaScript file or inline scripts

2. **Implement file upload**
   - File input element
   - Read file with FileReader
   - Display on canvas

3. **Add cropping functionality**
   - Integrate Cropper.js or build custom cropper
   - Ensure 1:1 aspect ratio
   - Add positioning guides

4. **Create print layout generator**
   - Calculate tile positions for 4x6 sheet
   - Draw cropped images onto print canvas
   - Add cut guides between photos

5. **Implement download**
   - Convert canvas to blob
   - Create download link
   - Trigger download

6. **Polish UI/UX**
   - Add instructions
   - Improve visual design
   - Test on various image sizes

## Deployment

### Hosting Options (all free)
- **GitHub Pages** - push to gh-pages branch
- **Netlify** - drag and drop or Git integration
- **Vercel** - Git integration with auto-deploy
- **Cloudflare Pages** - fast, global CDN

### Files to Deploy
- index.html
- style.css (or inline in HTML)
- script.js (or inline in HTML)
- Any library files if not using CDN

### No Backend Needed
- All processing happens client-side
- No storage, no database, no API
- Zero ongoing costs

## Testing Checklist

- [ ] Upload various image sizes and formats
- [ ] Crop selection works smoothly
- [ ] Final dimensions are exactly 600x600 pixels at 300 DPI
- [ ] Print sheet is exactly 1200x1800 pixels
- [ ] Downloaded file is high quality
- [ ] Works on desktop browsers
- [ ] Mobile responsive (if implemented)
- [ ] File size of output is reasonable (<2MB)

## Success Criteria

**Minimum Viable Product:**
- User can upload a photo
- User can crop to passport size
- Tool generates a printable 4x6 sheet
- User can download the result
- Image quality is suitable for printing

**Complete Product:**
- All MVP features plus smooth UX
- Clear instructions throughout
- Professional appearance
- Fast performance
- Works reliably across browsers

## Estimated Development Time

- **Basic working version:** 3-6 hours
- **Polished MVP:** 8-12 hours
- **Full-featured tool:** 20-30 hours

## Resources

### Documentation
- Canvas API: https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API
- FileReader API: https://developer.mozilla.org/en-US/docs/Web/API/FileReader
- Cropper.js: https://fengyuanchen.github.io/cropperjs/

### Passport Photo Standards
- US: https://travel.state.gov/content/travel/en/passports/how-apply/photos.html
- Standard dimensions: 2x2 inches, 51x51mm

### Image Quality
- Use 300 DPI minimum for printing
- JPEG quality 90+ or PNG for lossless
- sRGB color space for best printer compatibility

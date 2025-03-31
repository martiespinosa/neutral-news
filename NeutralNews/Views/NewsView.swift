//
//  NewsView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 1/7/25.
//

import SwiftUI
import UIKit

struct NewsView: View {
    let news: News
    let relatedNews: [News]
    
    @State private var dominantColor: Color = .gray
    
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                LinearGradient(colors: [dominantColor, dominantColor.opacity(0.3), .clear], startPoint: .top, endPoint: .bottom)
                    .ignoresSafeArea()
                
                ScrollView {
                    VStack {
                        VStack(alignment: .leading, spacing: 16) {
                            // TODO: Dejar solo la Image cuando haya el logo de todos los medios
                            if let uiImage = UIImage(named: news.sourceMedium.pressMedia.name.normalized()) {
                                Image(uiImage: uiImage)
                                    .resizable()
                                    .scaledToFit()
                                    .frame(height: 30)
                            } else {
                                Text(news.sourceMedium.pressMedia.name)
                                    .font(.title)
                                    .fontWeight(.semibold)
                                    .fontDesign(.serif)
                                    .foregroundColor(.secondary)
                            }
                            
                            Text(news.title)
                                .font(.title)
                                .fontWeight(.semibold)
                                .fontDesign(.serif)
                            
                            AsyncImage(url: URL(string: news.imageUrl ?? "")) { image in
                                image.image?
                                    .resizable()
                                    .scaledToFit()
                            }
                            .frame(maxWidth: .infinity)
                            .clipShape(.rect(cornerRadius: 16))
                            
                            Text(news.description)
                                .fontDesign(.serif)
                            
                            if let link = URL(string: news.link) {
                                Link("Leer en la fuente", destination: link)
                                    .fontDesign(.serif)
                            }
                        }
                        .padding()
                        
                        Spacer()
                        
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack {
                                ForEach(relatedNews) { new in
                                    NavigationLink(destination: NewsView(news: new, relatedNews: relatedNews)) {
                                        MediaHeadlineView(news: new)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            .padding(.leading, 16)
                        }
                    }
                    .frame(minHeight: geometry.size.height)
                    .onAppear {
                        Task {
                            dominantColor = await getDominantColor(from: news.imageUrl)
                        }
                    }
                }
            }
            .scrollBounceBehavior(.basedOnSize)
            .scrollIndicators(.hidden)
        }
    }
    
    @MainActor
    func getDominantColor(from urlString: String?) async -> Color {
        guard let urlString = urlString, let url = URL(string: urlString) else { return .gray }
        
        do {
            let (data, _) = try await URLSession.shared.data(from: url)
            guard let image = UIImage(data: data), let cgImage = image.cgImage else { return .gray }
            
            let width = 10, height = 10
            let context = CGContext(
                data: nil,
                width: width,
                height: height,
                bitsPerComponent: 8,
                bytesPerRow: width * 4,
                space: CGColorSpaceCreateDeviceRGB(),
                bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue
            )
            
            guard let context = context else { return .gray }
            context.draw(cgImage, in: CGRect(x: 0, y: 0, width: width, height: height))
            
            guard let data = context.data else { return .gray }
            
            var r = 0, g = 0, b = 0
            let pixelCount = width * height
            
            for i in stride(from: 0, to: pixelCount * 4, by: 4) {
                r += Int(data.load(fromByteOffset: i, as: UInt8.self))
                g += Int(data.load(fromByteOffset: i + 1, as: UInt8.self))
                b += Int(data.load(fromByteOffset: i + 2, as: UInt8.self))
            }
            
            return Color(red: Double(r) / Double(255 * pixelCount),
                         green: Double(g) / Double(255 * pixelCount),
                         blue: Double(b) / Double(255 * pixelCount))
        } catch {
            return .gray
        }
    }
}

#Preview {
    NewsView(news: .mock, relatedNews: [.mock, .mock, .mock])
}

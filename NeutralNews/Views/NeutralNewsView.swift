//
//  NeutralNewsView.swift
//  NeutralNews
//
//  Created by Martí Espinosa Farran on 13/4/25.
//

import SwiftUI
import UIKit

struct NeutralNewsView: View {
    let news: NeutralNews
    let imageUrl: String?
    let relatedNews: [News]
    var namespace: Namespace.ID
    
    @State private var dominantColor: Color = .gray
    
    var body: some View {
        GeometryReader { geometry in
            ZStack {
                LinearGradient(colors: [dominantColor, dominantColor.opacity(0.3), .clear], startPoint: .top, endPoint: .bottom)
                    .ignoresSafeArea()
                
                ScrollView {
                    VStack {
                        VStack(alignment: .leading, spacing: 16) {
//                            HStack {
//                                Text(news.category)
//                                Spacer()
//                                Text(news.pubDate)
//                            }
                            
                            Text(news.neutralTitle)
                                .font(.title)
                                .fontWeight(.semibold)
                                .fontDesign(.serif)
                            
                            AsyncImage(url: URL(string: imageUrl ?? "")) { phase in
                                switch phase {
                                case .empty:
                                    ShimmerView()
                                        .frame(height: 250)
                                case .success(let image):
                                    image
                                        .resizable()
                                        .scaledToFit()
                                case .failure:
                                    Image(systemName: "photo")
                                        .font(.largeTitle)
                                        .foregroundColor(.gray)
                                        .frame(height: 250)
                                @unknown default:
                                    EmptyView()
                                }
                            }
                            .frame(maxWidth: .infinity)
                            .clipShape(.rect(cornerRadius: 16))
                            
                            Text(news.neutralDescription)
//                                .fontDesign(.serif)
                        }
                        .padding()
                        
                        Spacer()
                        
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack {
                                ForEach(relatedNews) { new in
                                    NavigationLink {
                                        NewsView(news: new, relatedNews: relatedNews, namespace: namespace)
                                            .navigationTransition(.zoom(sourceID: new.id, in: namespace))
                                    } label: {
                                        MediaHeadlineView(news: new)
                                            .matchedTransitionSource(id: new.id, in: namespace)
                                    }
                                    .buttonStyle(.plain)
                                }
                            }
                            .padding(.leading, 16)
                        }
                    }
                    .frame(minHeight: geometry.size.height)
                    .task {
                        dominantColor = await getDominantColor(from: news.imageUrl)
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
    let namespace = Namespace().wrappedValue
    return NeutralNewsView(news: .mock, imageUrl: nil, relatedNews: [.mock, .mock, .mock], namespace: namespace)
}
